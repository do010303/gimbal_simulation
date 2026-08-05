#!/usr/bin/env python3
"""Throwaway M1 test stub — NOT the real M2 hardware adapter.

Serves lid/clamp/power/charge/cooling command services with instant
success, and republishes matching status topics so box_state_manager's
status-gated transitions (WAITING_BOX_CLAMP_OPEN, CLOSE_CLAMP_H/V,
CLOSE_LID) can actually progress without real box_simulation hardware.
"""
import rclpy
from rclpy.node import Node
from dib_msgs.msg import LidStatus, ClampStatus, ChargeStatus, CoolingStatus
from dib_msgs.srv import LidCmd, ClampCmd, ChargeCmd, CoolingCmd, PowerButtonCmd


class MockHwStub(Node):
    def __init__(self):
        super().__init__('mock_hw_stub')
        self.clamp_h = 0
        self.clamp_v = 0

        self.pub_lid = self.create_publisher(LidStatus, '/lid/status', 10)
        self.pub_clamp = self.create_publisher(ClampStatus, '/clamp/status', 10)
        self.pub_charge = self.create_publisher(ChargeStatus, '/dock/charge/status', 10)
        self.pub_cooling = self.create_publisher(CoolingStatus, '/dock/cooling_battery/status', 10)

        self.create_service(LidCmd, '/lid/cmd', self.on_lid_cmd)
        self.create_service(ClampCmd, '/clamp/cmd', self.on_clamp_cmd)
        self.create_service(PowerButtonCmd, '/dock/power_button/cmd', self.on_power_button_cmd)
        self.create_service(ChargeCmd, '/dock/charge/cmd', self.on_charge_cmd)
        self.create_service(CoolingCmd, '/dock/cooling_battery/cmd', self.on_cooling_cmd)

        # publish an initial CLOSED/closed-position status so the box
        # doesn't see stale zero-initialised fields as "already open"
        self.publish_clamp()
        self.publish_lid(LidStatus.CLOSED)

        self.get_logger().info('mock_hw_stub ready: /lid/cmd /clamp/cmd /dock/{power_button,charge,cooling_battery}/cmd')

    def publish_lid(self, status):
        msg = LidStatus()
        msg.lid_status = status
        self.pub_lid.publish(msg)

    def publish_clamp(self):
        msg = ClampStatus()
        msg.clamp_h_pos = self.clamp_h
        msg.clamp_v_pos = self.clamp_v
        self.pub_clamp.publish(msg)

    def on_lid_cmd(self, request, response):
        status = LidStatus.OPENED if request.command == 1 else LidStatus.CLOSED
        self.get_logger().info(f'/lid/cmd command={request.command} -> publishing lid_status={status}')
        self.publish_lid(status)
        response.success = True
        return response

    def on_clamp_cmd(self, request, response):
        # clamp_select: 1=H only, 2=V only, 3=both
        if request.clamp_select in (1, 3):
            self.clamp_h = request.clamp_h_pos_cmd
        if request.clamp_select in (2, 3):
            self.clamp_v = request.clamp_v_pos_cmd
        self.get_logger().info(
            f'/clamp/cmd select={request.clamp_select} h_cmd={request.clamp_h_pos_cmd} '
            f'v_cmd={request.clamp_v_pos_cmd} -> h={self.clamp_h} v={self.clamp_v}'
        )
        self.publish_clamp()
        response.success = True
        return response

    def on_power_button_cmd(self, request, response):
        self.get_logger().info(f'/dock/power_button/cmd command={request.command}')
        response.success = True
        return response

    def on_charge_cmd(self, request, response):
        self.get_logger().info(f'/dock/charge/cmd command={request.command}')
        msg = ChargeStatus()
        msg.charge_status = ChargeStatus.CHARGING if request.command == 1 else ChargeStatus.NOT_CHARGING
        self.pub_charge.publish(msg)
        response.success = True
        return response

    def on_cooling_cmd(self, request, response):
        self.get_logger().info(f'/dock/cooling_battery/cmd command={request.command}')
        msg = CoolingStatus()
        msg.cooling_status = 1 if request.command == 1 else 0
        self.pub_cooling.publish(msg)
        response.success = True
        return response


def main():
    rclpy.init()
    node = MockHwStub()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
