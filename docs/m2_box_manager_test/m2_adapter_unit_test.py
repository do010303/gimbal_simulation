#!/usr/bin/env python3
"""M2 adapter unit test — validates box_hardware_adapter WITHOUT Gazebo controllers.

box_simulation's ros2_control plugin cannot load under Gazebo Harmonic on Humble
(apt gz_ros2_control is built for Fortress -> missing GzPluginHook), so there is
no real controller_manager / joint_state_broadcaster. This test substitutes a
synthetic /joint_states publisher and exercises the adapter's two data paths
directly, proving the adapter code is correct independent of that infra issue:

  command path:  /lid/cmd, /clamp/cmd  -> correct JointTrajectory published
  status path:   synthetic /joint_states -> correct /lid/status, /clamp/status

Run box_hardware_adapter_node separately, then run this script.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory
from dib_msgs.msg import LidStatus, ClampStatus
from dib_msgs.srv import LidCmd, ClampCmd

LID_NAMES = {0: 'CLOSED', 1: 'OPENED', 2: 'CLOSING', 3: 'OPENING'}


class AdapterUnitTest(Node):
    def __init__(self):
        super().__init__('m2_adapter_unit_test')
        self.lid_traj = []      # captured lid JointTrajectory goals (target rad)
        self.clamp_h_traj = []
        self.clamp_v_traj = []
        self.lid_status_seen = set()
        self.clamp_status_samples = []

        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)
        self.create_subscription(JointTrajectory, '/joint_lid_controller/joint_trajectory',
                                 lambda m: self.lid_traj.append(m.points[0].positions[0]) if m.points else None, 10)
        self.create_subscription(JointTrajectory, '/joint_clamp_h_controller/joint_trajectory',
                                 lambda m: self.clamp_h_traj.append(m.points[0].positions[0]) if m.points else None, 10)
        self.create_subscription(JointTrajectory, '/joint_clamp_v_controller/joint_trajectory',
                                 lambda m: self.clamp_v_traj.append(m.points[0].positions[0]) if m.points else None, 10)
        self.create_subscription(LidStatus, '/lid/status', lambda m: self.lid_status_seen.add(m.lid_status), 10)
        self.create_subscription(ClampStatus, '/clamp/status',
                                 lambda m: self.clamp_status_samples.append((m.clamp_h_pos, m.clamp_v_pos)), 10)

        self.lid_cli = self.create_client(LidCmd, '/lid/cmd')
        self.clamp_cli = self.create_client(ClampCmd, '/clamp/cmd')

    def publish_joints(self, lid, ch, cv):
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name = ['lid_left_joint', 'lid_right_joint', 'clamp_h_1_joint',
                   'clamp_h_2_joint', 'clamp_v_1_joint', 'clamp_v_2_joint']
        js.position = [lid, lid, ch, ch, cv, cv]
        self.js_pub.publish(js)

    def spin(self, secs):
        end = time.time() + secs
        while rclpy.ok() and time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)


def main():
    rclpy.init()
    t = AdapterUnitTest()

    if not t.lid_cli.wait_for_service(timeout_sec=5.0) or not t.clamp_cli.wait_for_service(timeout_sec=5.0):
        t.get_logger().error('adapter services not available — is box_hardware_adapter_node running?')
        rclpy.shutdown()
        sys.exit(1)

    # --- Command path: /lid/cmd(open) -> lid trajectory target ~1.57 ---
    fut = t.lid_cli.call_async(LidCmd.Request(command=1))
    rclpy.spin_until_future_complete(t, fut, timeout_sec=3.0)
    t.spin(0.5)

    # /clamp/cmd both to 200 mm -> clamp trajectories ~0.2 m
    req = ClampCmd.Request(mode=0, clamp_h_pos_cmd=200, clamp_v_pos_cmd=200, clamp_select=3)
    fut = t.clamp_cli.call_async(req)
    rclpy.spin_until_future_complete(t, fut, timeout_sec=3.0)
    t.spin(0.5)

    # --- Status path: sweep synthetic /joint_states, lid 0 -> 1.57 ---
    for i in range(11):
        frac = i / 10.0
        t.publish_joints(lid=1.57 * frac, ch=0.2 * frac, cv=0.2 * frac)
        t.spin(0.1)
    t.spin(0.3)

    # ---- evaluate ----
    lid_cmd_ok = any(abs(p - 1.57) < 0.01 for p in t.lid_traj)
    clamp_h_ok = any(abs(p - 0.2) < 0.01 for p in t.clamp_h_traj)
    clamp_v_ok = any(abs(p - 0.2) < 0.01 for p in t.clamp_v_traj)
    lid_transient_ok = 3 in t.lid_status_seen  # OPENING seen during sweep up
    lid_opened_ok = 1 in t.lid_status_seen     # OPENED at the end
    clamp_mm_max = max((h for h, _ in t.clamp_status_samples), default=0)
    clamp_mm_ok = clamp_mm_max >= 195  # ~200 mm at full close (0.2 m * 1000)

    print('\n=== M2 ADAPTER UNIT TEST ===')
    print(f'  /lid/cmd(open) -> lid traj target 1.57 rad     : {"PASS" if lid_cmd_ok else "FAIL"}  (got {t.lid_traj})')
    print(f'  /clamp/cmd -> clamp_h traj 0.2 m               : {"PASS" if clamp_h_ok else "FAIL"}  (got {t.clamp_h_traj})')
    print(f'  /clamp/cmd -> clamp_v traj 0.2 m               : {"PASS" if clamp_v_ok else "FAIL"}  (got {t.clamp_v_traj})')
    print(f'  /lid/status OPENING seen during sweep          : {"PASS" if lid_transient_ok else "FAIL"}')
    print(f'  /lid/status OPENED at full open                : {"PASS" if lid_opened_ok else "FAIL"}')
    print(f'  /clamp/status reaches ~200 mm                  : {"PASS" if clamp_mm_ok else "FAIL"}  (max={clamp_mm_max} mm)')
    print(f'  /lid/status values seen: {sorted(LID_NAMES[s] for s in t.lid_status_seen)}')

    overall = all([lid_cmd_ok, clamp_h_ok, clamp_v_ok, lid_transient_ok, lid_opened_ok, clamp_mm_ok])
    print(f'\n  OVERALL: {"PASS" if overall else "FAIL"}')

    t.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if overall else 2)


if __name__ == '__main__':
    main()
