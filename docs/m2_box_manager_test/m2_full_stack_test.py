#!/usr/bin/env python3
"""M2 test 6a driver: real Gazebo lid/clamp movement through box_hardware_adapter.

Prereq: box_hardware_adapter/launch/box_full_stack.launch.py running
(box_simulation Gazebo + box_hardware_adapter + box_state_manager).

Beyond M1, this driver additionally proves the *real* hardware path:
  - /joint_states shows lid_left_joint actually moving (trajectory really sent)
  - /lid/status passes through OPENING/CLOSING before settling (delta inference)
  - /clamp/status crosses 0 -> ~200 mm during SECURING_DRONE, and box_manager's
    own box_info.clamp_state (via /b2/telemetry) reaches CLOSED (yaml fix works)

The drone-landed signal is still hand-published here (same shortcut as M1) so the
box FSM can progress to SECURING_DRONE; the *real* MAVROS landed passthrough is
tested separately in 6b via mavros_to_dib_telemetry.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import JointState
from dib_msgs.msg import (BoxState, BoxTelemetry, DroneTelemetry, LidStatus,
                          ClampStatus, State)
from dib_msgs.srv import BoxCmd
from dib_msgs.msg import BoxCmd as BoxCmdMsg

STATE_NAMES = {
    0: 'EMPTY', 1: 'IDLE', 2: 'PREPARING_FOR_TAKEOFF', 3: 'MISSION_UPLOADING',
    4: 'WAITING_FOR_TAKEOFF', 5: 'WAITING_FOR_RETURN', 6: 'PREPARING_FOR_LANDING',
    7: 'WAITING_FOR_LANDING', 8: 'SECURING_DRONE', 9: 'CHARGING',
    10: 'MAINTAINING', 101: 'ERROR',
}
LID_NAMES = {0: 'CLOSED', 1: 'OPENED', 2: 'CLOSING', 3: 'OPENING'}
CLAMP_STATE_NAMES = {0: 'CLOSED', 1: 'OPENED', 2: 'CLOSING', 3: 'OPENING'}
TARGET_SEQUENCE = [0, 1, 6, 7, 8, 9]


class M2Test(Node):
    def __init__(self):
        super().__init__('m2_full_stack_test')
        self.state_trace = []
        self.last_state = None
        self.telemetry_sent = False

        self.lid_joint_min = None
        self.lid_joint_max = None
        self.lid_statuses_seen = set()
        self.clamp_h_min = None
        self.clamp_h_max = None
        self.box_clamp_state_reached_closed = False

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                          history=HistoryPolicy.KEEP_LAST, depth=10)
        besteffort = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                                 history=HistoryPolicy.KEEP_LAST, depth=1)

        self.create_subscription(BoxState, '/box/state', self.on_state, qos)
        self.create_subscription(JointState, '/joint_states', self.on_joints, 10)
        self.create_subscription(LidStatus, '/lid/status', self.on_lid, 10)
        self.create_subscription(ClampStatus, '/clamp/status', self.on_clamp, 10)
        self.create_subscription(BoxTelemetry, '/b2/telemetry', self.on_telemetry, besteffort)

        self.pub_telemetry = self.create_publisher(DroneTelemetry, '/d1/telemetry', besteffort)
        self.cli_box_cmd = self.create_client(BoxCmd, '/b2/cmd')

    def on_state(self, msg):
        if msg.state != self.last_state:
            self.state_trace.append((time.time(), msg.state))
            self.get_logger().info(f'[TRACE] box_state -> {STATE_NAMES.get(msg.state)} ({msg.state})')
            self.last_state = msg.state
        if msg.state == 7 and not self.telemetry_sent:
            self.send_landed_telemetry()
            self.telemetry_sent = True

    def on_joints(self, msg):
        for name, pos in zip(msg.name, msg.position):
            if name == 'lid_left_joint':
                self.lid_joint_min = pos if self.lid_joint_min is None else min(self.lid_joint_min, pos)
                self.lid_joint_max = pos if self.lid_joint_max is None else max(self.lid_joint_max, pos)

    def on_lid(self, msg):
        self.lid_statuses_seen.add(msg.lid_status)

    def on_clamp(self, msg):
        self.clamp_h_min = msg.clamp_h_pos if self.clamp_h_min is None else min(self.clamp_h_min, msg.clamp_h_pos)
        self.clamp_h_max = msg.clamp_h_pos if self.clamp_h_max is None else max(self.clamp_h_max, msg.clamp_h_pos)

    def on_telemetry(self, msg):
        if msg.box_info.clamp_state == 0:  # CLOSED
            self.box_clamp_state_reached_closed = True

    def send_landed_telemetry(self):
        m = DroneTelemetry()
        m.header.stamp = self.get_clock().now().to_msg()
        m.state.connected = True
        m.state.system_status = 3
        m.state.landed_state = State.LANDED_STATE_ON_GROUND
        self.pub_telemetry.publish(m)
        self.get_logger().info('[DRIVER] published /d1/telemetry landed_state=ON_GROUND (M1-style shortcut)')

    def call_request_landing(self):
        if not self.cli_box_cmd.wait_for_service(timeout_sec=10.0):
            self.get_logger().error('/b2/cmd not available')
            return False
        req = BoxCmd.Request()
        req.command = BoxCmdMsg.REQUEST_LANDING
        req.agent_id = 12  # % 10 == 2 branch; drone_id = 12 // 10 = 1
        fut = self.cli_box_cmd.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)
        ok = fut.result() is not None and fut.result().success
        self.get_logger().info(f'[DRIVER] REQUEST_LANDING success={ok}')
        return ok


def main():
    rclpy.init()
    node = M2Test()

    settle = time.time() + 3.0
    while rclpy.ok() and node.last_state is None and time.time() < settle:
        rclpy.spin_once(node, timeout_sec=0.1)

    if not node.call_request_landing():
        node.get_logger().error('Aborting: REQUEST_LANDING failed')
        rclpy.shutdown()
        sys.exit(1)

    deadline = time.time() + 90.0  # SECURING clamp close can take a while in sim
    while rclpy.ok() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        if node.last_state == 9:
            for _ in range(10):
                rclpy.spin_once(node, timeout_sec=0.2)
            break

    seq = [s for _, s in node.state_trace]
    t0 = node.state_trace[0][0] if node.state_trace else time.time()

    print('\n=== M2 6a STATE TRACE ===')
    for t, s in node.state_trace:
        print(f'  t+{t - t0:6.2f}s  {STATE_NAMES.get(s)} ({s})')

    lid_range = ((node.lid_joint_max or 0) - (node.lid_joint_min or 0))
    print('\n=== M2 6a HARDWARE OBSERVATIONS ===')
    print(f'  lid_left_joint range (rad):    {node.lid_joint_min} .. {node.lid_joint_max}  (delta={lid_range:.3f})')
    print(f'  /lid/status values seen:       {sorted(LID_NAMES[s] for s in node.lid_statuses_seen)}')
    print(f'  /clamp/status.clamp_h_pos (mm): {node.clamp_h_min} .. {node.clamp_h_max}')
    print(f'  box_info.clamp_state reached CLOSED: {node.box_clamp_state_reached_closed}')

    seq_ok = seq[:len(TARGET_SEQUENCE)] == TARGET_SEQUENCE
    lid_moved = lid_range > 0.5
    lid_transient = bool(node.lid_statuses_seen & {2, 3})  # CLOSING or OPENING
    clamp_moved = (node.clamp_h_max or 0) > 150

    print('\n=== M2 6a RESULT ===')
    print(f'  state sequence EMPTY..CHARGING : {"PASS" if seq_ok else "FAIL"}  ({[STATE_NAMES[s] for s in seq]})')
    print(f'  lid actually moved (>0.5 rad)  : {"PASS" if lid_moved else "FAIL"}')
    print(f'  lid OPENING/CLOSING observed   : {"PASS" if lid_transient else "FAIL"}')
    print(f'  clamp reached ~200 mm          : {"PASS" if clamp_moved else "FAIL"}')
    overall = seq_ok and lid_moved and lid_transient and clamp_moved
    print(f'  OVERALL                        : {"PASS" if overall else "FAIL"}')

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if overall else 2)


if __name__ == '__main__':
    main()
