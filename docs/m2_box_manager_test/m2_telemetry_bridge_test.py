#!/usr/bin/env python3
"""M2 test 6b: real MAVROS landed passthrough via mavros_to_dib_telemetry.

Proves the drone-side half of M2: box_manager transitions
WAITING_FOR_LANDING -> SECURING_DRONE off a REAL PX4 land-detector signal
delivered by the telemetry bridge — with NO hand-published DroneTelemetry
(unlike the M1 shortcut).

Prereq terminals (see README):
  T1: PX4 SITL              (make px4_sitl gz_x500)  -> pxh> shell for flying
  T2: MAVROS               (ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580)
  T3: box_state_manager    (ros2 run box_manager box_state_manager_node --ros-args --params-file .../box_state_manager.yaml)
  T4: mock box hardware    (python3 .../m1_box_manager_test/mock_hw_stub.py)
  T5: telemetry bridge     (ros2 run precision_landing mavros_to_dib_telemetry --ros-args -p drone_id:=1)
  T6: this driver

Flight, done by YOU in the PX4 pxh> shell when prompted:
  pxh> commander takeoff     (wait until airborne)
  ... driver triggers REQUEST_LANDING, box reaches WAITING_FOR_LANDING ...
  pxh> commander land        (when the driver tells you to)

The driver watches everything and reports PASS/FAIL. It NEVER publishes
DroneTelemetry — the transition must come from the real bridge.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from mavros_msgs.msg import ExtendedState
from dib_msgs.msg import BoxState, DroneTelemetry
from dib_msgs.srv import BoxCmd
from dib_msgs.msg import BoxCmd as BoxCmdMsg

STATE_NAMES = {0: 'EMPTY', 1: 'IDLE', 6: 'PREPARING_FOR_LANDING', 7: 'WAITING_FOR_LANDING',
               8: 'SECURING_DRONE', 9: 'CHARGING', 101: 'ERROR'}
LANDED = {0: 'UNDEFINED', 1: 'ON_GROUND', 2: 'IN_AIR', 3: 'TAKEOFF', 4: 'LANDING'}


class BridgeTest(Node):
    def __init__(self):
        super().__init__('m2_telemetry_bridge_test')
        self.mavros_landed = None
        self.dib_landed = None
        self.box_state = None
        self.box_trace = []
        self.fidelity_samples = 0
        self.fidelity_persistent_mismatches = 0  # d1 wrong AFTER grace -> real fault
        self.fidelity_transient = 0              # d1 lagging within grace (expected)
        self.max_lag_s = 0.0
        self.mavros_change_t = 0.0
        self.fidelity_grace_s = 0.4              # bridge is event-driven; allow catch-up
        self.secured_landed_value = None  # landed_state seen at WAITING->SECURING

        besteffort = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                                 history=HistoryPolicy.KEEP_LAST, depth=1)
        reliable = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                               history=HistoryPolicy.KEEP_LAST, depth=10)

        self.create_subscription(ExtendedState, '/mavros/extended_state', self.on_ext, besteffort)
        self.create_subscription(DroneTelemetry, '/d1/telemetry', self.on_dib, besteffort)
        self.create_subscription(BoxState, '/box/state', self.on_box, reliable)
        self.cli = self.create_client(BoxCmd, '/b2/cmd')

    def on_ext(self, msg):
        if msg.landed_state != self.mavros_landed:
            self.mavros_change_t = time.time()  # bridge needs 1 msg to catch up
        self.mavros_landed = msg.landed_state
        self._sample_fidelity()

    def on_dib(self, msg):
        self.dib_landed = msg.state.landed_state
        self._sample_fidelity()

    def _sample_fidelity(self):
        # The bridge is event-driven: when /mavros/extended_state changes, d1 only
        # reflects it on the next republish (<~100 ms). Count a mismatch as a real
        # fault only if d1 fails to catch up within the grace window; a mismatch
        # inside the window is expected transient lag, not infidelity.
        if self.mavros_landed is None or self.dib_landed is None:
            return
        self.fidelity_samples += 1
        if self.mavros_landed != self.dib_landed:
            lag = time.time() - self.mavros_change_t
            self.max_lag_s = max(self.max_lag_s, lag)
            if lag > self.fidelity_grace_s:
                self.fidelity_persistent_mismatches += 1
            else:
                self.fidelity_transient += 1

    def on_box(self, msg):
        if msg.state != self.box_state:
            self.box_trace.append((time.time(), msg.state))
            self.get_logger().info(f'[TRACE] box_state -> {STATE_NAMES.get(msg.state, msg.state)}')
            if msg.state == 8 and self.box_state == 7:
                self.secured_landed_value = self.dib_landed
            self.box_state = msg.state

    def trigger_request_landing(self):
        if not self.cli.wait_for_service(timeout_sec=10.0):
            self.get_logger().error('/b2/cmd not available')
            return False
        req = BoxCmd.Request()
        req.command = BoxCmdMsg.REQUEST_LANDING
        req.agent_id = 12
        fut = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)
        ok = fut.result() is not None and fut.result().success
        self.get_logger().info(f'[DRIVER] REQUEST_LANDING success={ok}')
        return ok

    def wait_until(self, cond, timeout, msg):
        self.get_logger().info(msg)
        end = time.time() + timeout
        while rclpy.ok() and time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.1)
            if cond():
                return True
        return False


def main():
    rclpy.init()
    n = BridgeTest()

    # settle: get first samples
    n.wait_until(lambda: n.mavros_landed is not None and n.dib_landed is not None, 15.0,
                 '[DRIVER] waiting for /mavros/extended_state + /d1/telemetry ...')
    if n.mavros_landed is None:
        print('FAIL: no /mavros/extended_state — is PX4 SITL + MAVROS up?')
        rclpy.shutdown(); sys.exit(1)
    if n.dib_landed is None:
        print('FAIL: no /d1/telemetry — is mavros_to_dib_telemetry running?')
        rclpy.shutdown(); sys.exit(1)
    print(f'[DRIVER] bridge alive: mavros landed={LANDED.get(n.mavros_landed)}  d1={LANDED.get(n.dib_landed)}')

    # Phase 1: wait for takeoff (IN_AIR) so the box reaches WAITING while airborne
    print('\n>>> In the PX4 pxh> shell now run:  commander takeoff\n')
    if not n.wait_until(lambda: n.mavros_landed == 2, 60.0, '[DRIVER] waiting for drone IN_AIR ...'):
        print('FAIL: drone never reported IN_AIR (did you run commander takeoff?)')
        rclpy.shutdown(); sys.exit(2)
    print('[DRIVER] drone airborne.')

    # Phase 2: trigger landing request, wait for box WAITING_FOR_LANDING
    if not n.trigger_request_landing():
        rclpy.shutdown(); sys.exit(1)
    if not n.wait_until(lambda: n.box_state == 7, 40.0, '[DRIVER] waiting for box WAITING_FOR_LANDING ...'):
        print('FAIL: box did not reach WAITING_FOR_LANDING (mock hardware / box_manager issue)')
        rclpy.shutdown(); sys.exit(2)
    print('[DRIVER] box ready (WAITING_FOR_LANDING), drone still airborne.')

    # Phase 3: land, expect box -> SECURING off real telemetry
    print('\n>>> Now in the PX4 pxh> shell run:  commander land\n')
    if not n.wait_until(lambda: n.box_state == 8, 90.0, '[DRIVER] waiting for box SECURING_DRONE (real landed signal) ...'):
        print('FAIL: box did not transition to SECURING_DRONE after landing')
        print(f'      last mavros landed={LANDED.get(n.mavros_landed)} d1={LANDED.get(n.dib_landed)} box={STATE_NAMES.get(n.box_state)}')
        rclpy.shutdown(); sys.exit(2)

    # ---- evaluate ----
    fidelity_ok = n.fidelity_samples > 0 and n.fidelity_persistent_mismatches == 0
    secured_on_ground = n.secured_landed_value == 1
    box_seq = [s for _, s in n.box_trace]

    print('\n=== M2 6b RESULT ===')
    print(f'  box_state trace: {[STATE_NAMES.get(s, s) for s in box_seq]}')
    print(f'  bridge fidelity: samples={n.fidelity_samples}, '
          f'persistent_mismatch={n.fidelity_persistent_mismatches}, '
          f'transient_lag={n.fidelity_transient} (max {n.max_lag_s*1000:.0f} ms): '
          f'{"PASS" if fidelity_ok else "FAIL"}')
    print(f'  box WAITING_FOR_LANDING -> SECURING_DRONE happened: {"PASS" if 8 in box_seq and 7 in box_seq else "FAIL"}')
    print(f'  landed_state at that transition was ON_GROUND: {"PASS" if secured_on_ground else "FAIL"} '
          f'(got {LANDED.get(n.secured_landed_value)})')
    print('  (no DroneTelemetry was hand-published by this driver)')

    overall = fidelity_ok and (8 in box_seq and 7 in box_seq) and secured_on_ground
    print(f'\n  OVERALL: {"PASS" if overall else "FAIL"}')

    n.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if overall else 2)


if __name__ == '__main__':
    main()
