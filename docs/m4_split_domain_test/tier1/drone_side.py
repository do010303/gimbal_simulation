#!/usr/bin/env python3
"""Tier-1 fake DRONE side (run with ROS_DOMAIN_ID=0).

Stands in for the drone computer without MAVROS/Gazebo. It:
  - publishes /d1/telemetry (DroneTelemetry) BEST_EFFORT/VOLATILE with
    state.system_status = 111 as a fingerprint the box side recognises,
  - subscribes /b2/telemetry and logs when box_state=9 arrives over the bridge,
  - publishes /b2/drone_cmd REQUEST_LANDING every 3 s, mirroring the real
    BoxLink::request_landing() retry cadence (REQUEST_RETRY_SEC = 3.0).

The command path is a TOPIC now, not the old /b2/cmd service, so there is no
reply to wait on -- exactly like the real BoxLink, which confirms landing from
telemetry (box_state == WAITING_FOR_LANDING) rather than from any ack. Watch
the BOX terminal to see the command land.

Pair with box_side.py (ROS_DOMAIN_ID=42) and a bridge -- either
`ddsrouter -c .../dds_router_split.yaml` (default) or
`ros2 run dib_domain_bridge dib_split_bridge 42 0` (fallback).
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from dib_msgs.msg import BoxTelemetry, DroneTelemetry, BoxCmd

REQUEST_LANDING = 23
DRONE_ID = 1
AGENT_ROLE_DRONE = 2          # box routes on agent_id % 10; 2 == drone
AGENT_ID = DRONE_ID * 10 + AGENT_ROLE_DRONE


class DroneSide(Node):
    def __init__(self):
        super().__init__('tier1_drone_side')
        qos = QoSProfile(depth=1)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT
        qos.durability = DurabilityPolicy.VOLATILE
        qos.history = HistoryPolicy.KEEP_LAST
        self.pub = self.create_publisher(DroneTelemetry, '/d1/telemetry', qos)
        self.sub = self.create_subscription(
            BoxTelemetry, '/b2/telemetry', self.on_box, 10)
        # Same topic + depth the real BoxLink uses.
        self.cmd_pub = self.create_publisher(BoxCmd, '/b2/drone_cmd', 10)
        self.create_timer(0.5, self.tick)
        self.create_timer(3.0, self.send_cmd)      # BoxLink REQUEST_RETRY_SEC
        self.saw_box = False
        self.sent = 0
        self.get_logger().info('DRONE up: publishing /d1/telemetry (system_status=111), '
                               'listening /b2/telemetry, publishing /b2/drone_cmd every 3s')

    def tick(self):
        msg = DroneTelemetry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.state.system_status = 111    # fingerprint
        msg.state.connected = True
        self.pub.publish(msg)

    def on_box(self, msg):
        if not self.saw_box:
            self.saw_box = True
            self.get_logger().info(
                f'>>> /b2/telemetry ARRIVED over bridge: box_state={msg.box_state.state} '
                f'box_id={msg.box_info.box_id}  (bridge box->drone OK)')

    def send_cmd(self):
        msg = BoxCmd()
        msg.command = REQUEST_LANDING
        msg.agent_id = AGENT_ID
        msg.reserve = 0
        self.cmd_pub.publish(msg)
        self.sent += 1
        self.get_logger().info(
            f'<<< published /b2/drone_cmd #{self.sent}: REQUEST_LANDING '
            f'agent_id={AGENT_ID}  (check the BOX terminal for arrival)')


def main():
    rclpy.init()
    node = DroneSide()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
