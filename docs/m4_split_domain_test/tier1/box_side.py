#!/usr/bin/env python3
"""Tier-1 fake BOX side (run with ROS_DOMAIN_ID=42).

Stands in for the whole box computer without Gazebo/PX4. It:
  - publishes /b2/telemetry (BoxTelemetry) with box_state.state = CHARGING(9)
    as a fingerprint the drone side can recognise across the bridge,
  - subscribes /b2/drone_cmd (BoxCmd) and logs each command, mirroring
    box_state_manager::drone_cmd_callback (which routes on agent_id % 10 == 2).

/b2/drone_cmd is a TOPIC, not the old /b2/cmd service: the service reply never
crossed a DDS-Router domain boundary, and it was dead weight anyway
(box_state_manager set success=true before doing any work). See
precision_landing/config/dds_router_split.yaml for the full rationale.

Pair with drone_side.py (ROS_DOMAIN_ID=0) and a bridge -- either
`ddsrouter -c .../dds_router_split.yaml` (default) or
`ros2 run dib_domain_bridge dib_split_bridge 42 0` (fallback). No Gazebo needed.
"""
import rclpy
from rclpy.node import Node
from dib_msgs.msg import BoxTelemetry, BoxCmd

# BoxCmd command constants worth naming here (see dib_msgs/msg/BoxCmd.msg).
REQUEST_LANDING = 23
TURN_OFF_DRONE = 4


class BoxSide(Node):
    def __init__(self):
        super().__init__('tier1_box_side')
        self.pub = self.create_publisher(BoxTelemetry, '/b2/telemetry', 10)
        self.sub = self.create_subscription(
            BoxCmd, '/b2/drone_cmd', self.on_drone_cmd, 10)
        self.create_timer(0.5, self.tick)
        self.seen = 0
        self.get_logger().info(
            'BOX up: publishing /b2/telemetry (box_state=9), listening /b2/drone_cmd')

    def tick(self):
        msg = BoxTelemetry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.box_state.state = 9          # CHARGING — the fingerprint
        msg.box_info.box_id = 2
        self.pub.publish(msg)

    def on_drone_cmd(self, msg):
        # Same routing rule as the real box_state_manager: only agent_id % 10 == 2
        # is the drone role; anything else belongs to the operator/server path
        # (which still uses the /b2/cmd service and does NOT cross domains).
        if msg.agent_id % 10 != 2:
            self.get_logger().warn(
                f'/b2/drone_cmd IGNORED: agent_id={msg.agent_id} is not the drone role')
            return
        self.seen += 1
        name = {REQUEST_LANDING: 'REQUEST_LANDING',
                TURN_OFF_DRONE: 'TURN_OFF_DRONE'}.get(msg.command, f'cmd{msg.command}')
        self.get_logger().info(
            f'>>> /b2/drone_cmd #{self.seen} ARRIVED over bridge: {name} '
            f'(command={msg.command} agent_id={msg.agent_id} drone_id={msg.agent_id // 10})'
            '  (bridge drone->box OK)')


def main():
    rclpy.init()
    node = BoxSide()
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
