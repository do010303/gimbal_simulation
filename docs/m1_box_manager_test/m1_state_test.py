#!/usr/bin/env python3
"""M1 acceptance driver: drives box_state_manager through
EMPTY -> IDLE -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING ->
SECURING_DRONE -> CHARGING by calling BoxCmd::REQUEST_LANDING and
publishing one DroneTelemetry(ON_GROUND) sample, then reports the
full state trace observed on /box/state.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from dib_msgs.msg import BoxState, DroneTelemetry, State
from dib_msgs.srv import BoxCmd
from dib_msgs.msg import BoxCmd as BoxCmdMsg

STATE_NAMES = {
    0: 'EMPTY', 1: 'IDLE', 2: 'PREPARING_FOR_TAKEOFF', 3: 'MISSION_UPLOADING',
    4: 'WAITING_FOR_TAKEOFF', 5: 'WAITING_FOR_RETURN', 6: 'PREPARING_FOR_LANDING',
    7: 'WAITING_FOR_LANDING', 8: 'SECURING_DRONE', 9: 'CHARGING',
    10: 'MAINTAINING', 101: 'ERROR',
}

TARGET_SEQUENCE = [0, 1, 6, 7, 8, 9]  # EMPTY -> IDLE -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING -> SECURING_DRONE -> CHARGING


class M1Test(Node):
    def __init__(self):
        super().__init__('m1_state_test')
        self.trace = []
        self.last_state = None
        self.telemetry_sent = False

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                          history=HistoryPolicy.KEEP_LAST, depth=10)
        self.sub_state = self.create_subscription(BoxState, '/box/state', self.on_state, qos)
        self.pub_telemetry = self.create_publisher(DroneTelemetry, '/d1/telemetry', 10)
        self.cli_box_cmd = self.create_client(BoxCmd, '/b2/cmd')

    def on_state(self, msg: BoxState):
        name = STATE_NAMES.get(msg.state, f'UNKNOWN({msg.state})')
        if msg.state != self.last_state:
            t = time.time()
            self.trace.append((t, msg.state, name))
            self.get_logger().info(f'[TRACE] box_state -> {name} ({msg.state})')
            self.last_state = msg.state

        # Once box says it's waiting for the drone to land, tell it the
        # drone is on the ground (stand-in for the future MAVROS->dib_msgs
        # telemetry bridge from M4/M2).
        if msg.state == 7 and not self.telemetry_sent:
            self.send_landed_telemetry()
            self.telemetry_sent = True

    def send_landed_telemetry(self):
        msg = DroneTelemetry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.state.connected = True
        msg.state.system_status = 3
        msg.state.landed_state = State.LANDED_STATE_ON_GROUND
        self.pub_telemetry.publish(msg)
        self.get_logger().info('[DRIVER] published /d1/telemetry landed_state=ON_GROUND')

    def call_request_landing(self):
        if not self.cli_box_cmd.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('/b2/cmd service not available')
            return False
        req = BoxCmd.Request()
        req.command = BoxCmdMsg.REQUEST_LANDING
        req.agent_id = 12  # agent_id % 10 == 2 branch, drone_id = agent_id // 10 = 1
        future = self.cli_box_cmd.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result() is None:
            self.get_logger().error('BoxCmd REQUEST_LANDING call failed (no response)')
            return False
        self.get_logger().info(f'[DRIVER] BoxCmd REQUEST_LANDING response success={future.result().success}')
        return True


def main():
    rclpy.init()
    node = M1Test()

    # let DDS discovery settle and capture the node's real starting state
    # (EMPTY) before we kick the FSM, so the trace is complete.
    settle_deadline = time.time() + 3.0
    while rclpy.ok() and node.last_state is None and time.time() < settle_deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if node.last_state is None:
        node.get_logger().warn('No /box/state received yet before triggering — proceeding anyway')

    ok = node.call_request_landing()
    if not ok:
        node.get_logger().error('Aborting: could not send REQUEST_LANDING')
        rclpy.shutdown()
        sys.exit(1)

    deadline = time.time() + 25.0
    while rclpy.ok() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
        if node.last_state == 9:  # CHARGING reached
            time.sleep(0.5)  # drain a couple more state callbacks if any
            rclpy.spin_once(node, timeout_sec=0.2)
            break

    seq = [s for _, s, _ in node.trace]
    print('\n=== M1 STATE TRACE ===')
    t0 = node.trace[0][0] if node.trace else time.time()
    for t, s, name in node.trace:
        print(f'  t+{t - t0:5.2f}s  {name} ({s})')

    passed = seq == TARGET_SEQUENCE or (len(seq) >= len(TARGET_SEQUENCE) and seq[:len(TARGET_SEQUENCE)] == TARGET_SEQUENCE)
    print(f'\nExpected sequence: {[STATE_NAMES[s] for s in TARGET_SEQUENCE]}')
    print(f'Observed sequence: {[STATE_NAMES[s] for s in seq]}')
    print(f'RESULT: {"PASS" if passed else "FAIL"}')

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if passed else 2)


if __name__ == '__main__':
    main()
