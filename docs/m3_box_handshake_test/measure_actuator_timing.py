#!/usr/bin/env python3
"""
Passive observer: measure box actuator open/close TIMES (REQ_BOX_PHY_0005/0006).

Listens (does not command) to:
  /lid/status   (dib_msgs/LidStatus)   -- door mechanism
  /clamp/status (dib_msgs/ClampStatus) -- UAV-alignment clamp (h + v axes, mm)

Prints each completed motion with its duration. The spec gives no time
threshold, so this only REPORTS measured values (no PASS/FAIL). Run it during a
normal M3 loop; the securing sequence exercises both mechanisms.

    python3 docs/m3_box_handshake_test/measure_actuator_timing.py
"""
import rclpy
from rclpy.node import Node
from dib_msgs.msg import LidStatus, ClampStatus

LID_NAME = {0: 'CLOSED', 1: 'OPENED', 2: 'CLOSING', 3: 'OPENING'}
STABLE_S = 0.7      # position unchanged this long => motion finished
MOVE_EPS = 2        # mm change counted as movement


class ActuatorTiming(Node):
    def __init__(self):
        super().__init__('measure_actuator_timing')
        self.create_subscription(LidStatus, '/lid/status', self.on_lid, 10)
        self.create_subscription(ClampStatus, '/clamp/status', self.on_clamp, 10)
        # lid: remember when a transition-in-progress state began
        self.lid_prev = None
        self.lid_open_start = None
        self.lid_close_start = None
        # clamp per-axis: (last_pos, move_start_t, last_change_t, from_pos)
        self.axis = {'h': self._new_axis(), 'v': self._new_axis()}
        self.create_timer(0.1, self.tick_clamp_settle)
        self.get_logger().info('Measuring /lid/status + /clamp/status timing. '
                               'Run an M3 loop; Ctrl-C when done.')

    def _new_axis(self):
        return {'last': None, 'start': None, 'last_change': None, 'from': None}

    def _t(self):
        return self.get_clock().now().nanoseconds / 1e9

    # ---- lid ----
    def on_lid(self, msg):
        s = msg.lid_status
        if s == self.lid_prev:
            return
        now = self._t()
        if s == 3:      # OPENING
            self.lid_open_start = now
        elif s == 1:    # OPENED
            if self.lid_open_start is not None:
                self.get_logger().info(
                    f'[LID] OPEN  took {now - self.lid_open_start:.2f}s')
                self.lid_open_start = None
        elif s == 2:    # CLOSING
            self.lid_close_start = now
        elif s == 0:    # CLOSED
            if self.lid_close_start is not None:
                self.get_logger().info(
                    f'[LID] CLOSE took {now - self.lid_close_start:.2f}s')
                self.lid_close_start = None
        self.lid_prev = s

    # ---- clamp (h + v axes) ----
    def on_clamp(self, msg):
        now = self._t()
        self._axis_update('h', msg.clamp_h_pos, now)
        self._axis_update('v', msg.clamp_v_pos, now)

    def _axis_update(self, name, pos, now):
        a = self.axis[name]
        if a['last'] is None:
            a['last'] = pos
            return
        if abs(pos - a['last']) >= MOVE_EPS:
            if a['start'] is None:
                a['start'] = now
                a['from'] = a['last']
            a['last_change'] = now
        a['last'] = pos

    def tick_clamp_settle(self):
        now = self._t()
        for name, a in self.axis.items():
            if a['start'] is not None and a['last_change'] is not None:
                if now - a['last_change'] >= STABLE_S:
                    dur = a['last_change'] - a['start']
                    direction = 'CLOSE' if a['last'] > a['from'] else 'OPEN'
                    self.get_logger().info(
                        f'[CLAMP-{name.upper()}] {direction} '
                        f'{a["from"]}->{a["last"]}mm took {dur:.2f}s')
                    a['start'] = None
                    a['last_change'] = None
                    a['from'] = None


def main():
    rclpy.init()
    node = ActuatorTiming()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
