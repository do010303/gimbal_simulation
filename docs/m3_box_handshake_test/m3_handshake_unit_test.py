#!/usr/bin/env python3
"""
M3 unit test - box handshake FSM (PRELANDING_CHECK / WAIT_BOX_READY).

Proves the two new states and the BoxLink service contract WITHOUT PX4, Gazebo
or MAVROS. Everything the controller talks to is mocked here:

  MAVROS side : /mavros/state, /mavros/extended_state,
                /mavros/local_position/pose, /mavros/global_position/global,
                and the set_mode / arming / command / param / mission services.
  Box side    : /b1/telemetry publisher + /b1/cmd service.

What is asserted:
  1. FSM reaches GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START.
     (Catches a missing can_transition() whitelist edge, which would otherwise
     fail silently and leave the drone stuck.)
  2. The box receives exactly one accepted BoxCmd REQUEST_LANDING(23) with
     agent_id == drone_id*10 + 2 == 12, matching box_state_manager.cpp's
     `agent_id % 10 == 2` drone branch.
  3. The controller does NOT leave WAIT_BOX_READY until the box publishes
     box_state == WAITING_FOR_LANDING(7).

Run (controller in another terminal):
  ros2 run precision_landing offboard_precland_controller --ros-args \
    --params-file src/precision_landing/config/offboard_precland_params.yaml
"""

import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import NavSatFix, CameraInfo
from mavros_msgs.msg import State, ExtendedState
from mavros_msgs.srv import CommandBool, SetMode, CommandLong, ParamGet, ParamSet, WaypointPull
from dib_msgs.msg import BoxTelemetry, BoxCmd
from dib_msgs.srv import BoxCmd as BoxCmdSrv

# Must match the controller's declared params.
DRONE_ID = 1
BOX_ID = 2      # must match box_state_manager.yaml (box_id: 2) and
                # offboard_precland_params.yaml (box_id: 2)
EXPECTED_AGENT_ID = DRONE_ID * 10 + 2  # box_state_manager.cpp: agent_id % 10 == 2

BOX_STATE_EMPTY = 0
BOX_STATE_WAITING_FOR_LANDING = 7

# Seconds the box "spends" opening lid + clamps before declaring itself ready.
BOX_PREPARE_SEC = 5.0


def pose_qos():
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST, depth=1,
        reliability=QoSReliabilityPolicy.BEST_EFFORT,
        durability=QoSDurabilityPolicy.VOLATILE)


def state_qos():
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST, depth=1,
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)


class M3HandshakeTest(Node):
    def __init__(self):
        super().__init__('m3_handshake_test')

        # --- mocked MAVROS publishers ---
        self.pub_state = self.create_publisher(State, '/mavros/state', state_qos())
        self.pub_ext = self.create_publisher(ExtendedState, '/mavros/extended_state', state_qos())
        self.pub_pose = self.create_publisher(PoseStamped, '/mavros/local_position/pose', pose_qos())
        self.pub_gps = self.create_publisher(NavSatFix, '/mavros/global_position/global', pose_qos())
        # PRELANDING_CHECK requires a live camera pipeline (M3): without this
        # the controller correctly refuses to ask the box to open its lid.
        self.pub_caminfo = self.create_publisher(CameraInfo, '/gimbal_camera/camera_info', 10)

        # --- mocked MAVROS services ---
        self.create_service(SetMode, '/mavros/set_mode', self.on_set_mode)
        self.create_service(CommandBool, '/mavros/cmd/arming', self.on_arming)
        self.create_service(CommandLong, '/mavros/cmd/command', self.on_command)
        self.create_service(ParamGet, '/mavros/param/get', self.on_param_get)
        self.create_service(ParamSet, '/mavros/param/set', self.on_param_set)
        self.create_service(WaypointPull, '/mavros/mission/pull', self.on_wp_pull)

        # --- mocked box ---
        self.pub_box_tlm = self.create_publisher(BoxTelemetry, f'/b{BOX_ID}/telemetry', 10)
        self.create_service(BoxCmdSrv, f'b{BOX_ID}/cmd', self.on_box_cmd)

        # --- observe the controller FSM ---
        self.create_subscription(String, '/lander/state', self.on_lander_state, 10)

        # mocked vehicle/box world state
        self.mode = 'AUTO.LAND'      # drives st_flight_in_progress()
        self.box_state = BOX_STATE_EMPTY
        self.box_prepare_start = None

        # observations
        self.fsm_trace = []
        self.box_cmds = []           # (agent_id, command, box_state_at_receipt)
        self.state_when_request = None
        self.t_enter_wait_box = None
        self.t_box_ready = None
        self.t_leave_wait_box = None

        self.create_timer(0.05, self.tick)   # 20 Hz mocked telemetry
        self.t0 = time.time()

    # ---------- mocked MAVROS service handlers ----------
    def on_set_mode(self, req, res):
        # The controller asks for OFFBOARD; reflect it back on /mavros/state so
        # st_goto_box()'s `current_mode_ != "OFFBOARD"` guard opens.
        if req.custom_mode:
            self.mode = req.custom_mode
            self.get_logger().info(f'[mock mavros] set_mode -> {self.mode}')
        res.mode_sent = True
        return res

    def on_arming(self, req, res):
        res.success = True
        res.result = 0
        return res

    def on_command(self, req, res):
        # Gimbal configure/control. Merely answering makes the controller set
        # gimbal_configured_ = true, which PRELANDING_CHECK gates on.
        res.success = True
        res.result = 0
        return res

    def on_param_get(self, req, res):
        res.success = True
        res.value.integer = 0
        res.value.real = 1.0
        return res

    def on_param_set(self, req, res):
        res.success = True
        return res

    def on_wp_pull(self, req, res):
        res.success = True
        res.wp_received = 0
        return res

    # ---------- mocked box ----------
    def on_box_cmd(self, req, res):
        self.box_cmds.append((req.agent_id, req.command, self.box_state))
        self.get_logger().info(
            f'[mock box] BoxCmd command={req.command} agent_id={req.agent_id} '
            f'(box_state={self.box_state})')

        # Mirror box_state_manager.cpp: drone branch is agent_id % 10 == 2, and
        # REQUEST_LANDING is only accepted while the box is EMPTY.
        if req.agent_id % 10 == 2 and req.command == BoxCmd.REQUEST_LANDING:
            if self.box_state == BOX_STATE_EMPTY:
                self.state_when_request = self.fsm_trace[-1] if self.fsm_trace else None
                self.box_prepare_start = time.time()
                self.get_logger().info(
                    f'[mock box] REQUEST_LANDING accepted, preparing for '
                    f'{BOX_PREPARE_SEC}s before WAITING_FOR_LANDING')
                res.success = True
                return res
        res.success = False
        return res

    # ---------- observation ----------
    def on_lander_state(self, msg):
        if not self.fsm_trace or self.fsm_trace[-1] != msg.data:
            self.fsm_trace.append(msg.data)
            self.get_logger().info(f'[FSM] -> {msg.data}')
            if msg.data == 'WAIT_BOX_READY':
                self.t_enter_wait_box = time.time()
            if self.t_enter_wait_box and self.t_leave_wait_box is None \
                    and msg.data not in ('WAIT_BOX_READY',):
                if len(self.fsm_trace) >= 2 and self.fsm_trace[-2] == 'WAIT_BOX_READY':
                    self.t_leave_wait_box = time.time()

    # ---------- 20 Hz mocked world ----------
    def tick(self):
        now = self.get_clock().now().to_msg()

        st = State()
        st.header.stamp = now
        st.connected = True
        st.armed = True
        st.guided = True
        st.mode = self.mode
        st.system_status = 4
        self.pub_state.publish(st)

        ext = ExtendedState()
        ext.landed_state = ExtendedState.LANDED_STATE_IN_AIR
        self.pub_ext.publish(ext)

        # Drone parked at 10 m, directly over the box (dx=dy=0 -> arrival is
        # immediate, so the test exercises the handshake, not the navigation).
        p = PoseStamped()
        p.header.stamp = now
        p.header.frame_id = 'map'
        p.pose.position.x = 0.0
        p.pose.position.y = 0.0
        p.pose.position.z = 10.0
        p.pose.orientation.w = 1.0
        self.pub_pose.publish(p)

        gps = NavSatFix()
        gps.header.stamp = now
        gps.latitude = 47.3977419
        gps.longitude = 8.5455938
        gps.altitude = 500.0
        self.pub_gps.publish(gps)

        ci = CameraInfo()
        ci.header.stamp = now
        ci.header.frame_id = 'camera_link'
        ci.width = 1280
        ci.height = 720
        self.pub_caminfo.publish(ci)

        # Box "prepares" for a while, then reports WAITING_FOR_LANDING.
        if self.box_prepare_start is not None and self.box_state == BOX_STATE_EMPTY:
            if time.time() - self.box_prepare_start >= BOX_PREPARE_SEC:
                self.box_state = BOX_STATE_WAITING_FOR_LANDING
                self.t_box_ready = time.time()
                self.get_logger().info('[mock box] now WAITING_FOR_LANDING(7)')

        tlm = BoxTelemetry()
        tlm.header.stamp = now
        tlm.box_info.latitude = gps.latitude     # same spot -> dist ~ 0
        tlm.box_info.longitude = gps.longitude
        tlm.box_info.yaw = 0.0
        tlm.box_state.state = self.box_state
        self.pub_box_tlm.publish(tlm)


def main():
    rclpy.init()
    node = M3HandshakeTest()
    print('\n=== M3 handshake unit test ===')
    print('Mocking MAVROS + box. Waiting for the controller FSM...\n')

    deadline = time.time() + 60.0
    try:
        while rclpy.ok() and time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if 'START' in node.fsm_trace:
                # Let a moment pass so the trace settles.
                end = time.time() + 1.0
                while time.time() < end:
                    rclpy.spin_once(node, timeout_sec=0.1)
                break
    except KeyboardInterrupt:
        pass

    trace = node.fsm_trace
    print('\n--- FSM trace ---')
    print(' -> '.join(trace) if trace else '(nothing seen on /lander/state)')

    print('\n--- BoxCmd requests seen by the mock box ---')
    for agent_id, cmd, bs in node.box_cmds:
        print(f'  command={cmd} agent_id={agent_id} (box_state={bs})')
    if not node.box_cmds:
        print('  (none)')

    # ---------- criteria ----------
    results = []

    required = ['GOTO_BOX', 'PRELANDING_CHECK', 'WAIT_BOX_READY', 'START']
    idxs = [trace.index(s) for s in required if s in trace]
    seq_ok = len(idxs) == len(required) and idxs == sorted(idxs)
    results.append((
        'FSM passes GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START',
        seq_ok,
        'all four states in order' if seq_ok
        else f'missing/ out of order: {[s for s in required if s not in trace]}'))

    landing_reqs = [c for c in node.box_cmds if c[1] == BoxCmd.REQUEST_LANDING]
    accepted = [c for c in landing_reqs if c[0] % 10 == 2 and c[2] == BOX_STATE_EMPTY]
    results.append((
        f'REQUEST_LANDING sent with agent_id == {EXPECTED_AGENT_ID}',
        len(accepted) >= 1 and all(c[0] == EXPECTED_AGENT_ID for c in landing_reqs),
        f'{len(landing_reqs)} request(s), agent_ids={[c[0] for c in landing_reqs]}'))

    results.append((
        'REQUEST_LANDING accepted exactly once (idempotent, no spam)',
        len(accepted) == 1,
        f'{len(accepted)} accepted, {len(landing_reqs)} total sent'))

    # The controller must wait for the box, not run ahead of it.
    waited = (node.t_box_ready is not None and node.t_leave_wait_box is not None
              and node.t_leave_wait_box >= node.t_box_ready - 0.05)
    held = None
    if node.t_enter_wait_box and node.t_leave_wait_box:
        held = node.t_leave_wait_box - node.t_enter_wait_box
    results.append((
        'Left WAIT_BOX_READY only after box reported WAITING_FOR_LANDING(7)',
        waited,
        f'held station {held:.1f}s (box prepared for {BOX_PREPARE_SEC}s)'
        if held is not None else 'never left WAIT_BOX_READY'))

    print('\n--- criteria ---')
    for name, ok, detail in results:
        print(f'  [{"PASS" if ok else "FAIL"}] {name}\n         {detail}')

    overall = all(ok for _, ok, _ in results)
    print(f'\n=== M3 unit test: {"PASS" if overall else "FAIL"} ===\n')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
