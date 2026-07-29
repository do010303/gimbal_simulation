#!/usr/bin/env python3
"""
7b — full closed-loop monitor (PASSIVE).

Publishes NOTHING and calls NO service. It only listens, so a PASS here cannot
be an artifact of the test harness poking the system -- that was the exact
criticism that made M2's 6b result need re-analysis. Everything below is
observed from the real drone and the real box.

Watches:
  /lander/state          drone FSM  (std_msgs/String)
  /box/state             box FSM    (dib_msgs/BoxState)
  /b2/telemetry          box telemetry (box_state + box GPS)
  /d1/telemetry          drone telemetry produced by the M2 bridge
  /mavros/extended_state ground truth for landed_state

Pass criteria:
  1. Drone FSM covers GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START
     and finishes at DONE.
  2. Box FSM covers EMPTY -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING
     -> SECURING_DRONE.
  3. The box left EMPTY only AFTER the drone entered WAIT_BOX_READY -- proves
     the drone's own REQUEST_LANDING caused it, not a leftover/manual trigger.
  4. The drone entered START only AFTER the box reached WAITING_FOR_LANDING.
  5. Box reached SECURING_DRONE after the real land detector fired
     (/mavros/extended_state -> ON_GROUND), via the M2 bridge.

Ctrl+C to stop and print the report.
"""

import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy

from std_msgs.msg import String
from mavros_msgs.msg import ExtendedState
from dib_msgs.msg import BoxState, BoxTelemetry, DroneTelemetry

BOX_ID = 2      # box_state_manager.yaml -> box_id: 2
DRONE_ID = 1

BOX_NAMES = {
    0: 'EMPTY', 1: 'IDLE', 2: 'PREPARING_FOR_TAKEOFF', 3: 'MISSION_UPLOADING',
    4: 'WAITING_FOR_TAKEOFF', 5: 'WAITING_FOR_RETURN', 6: 'PREPARING_FOR_LANDING',
    7: 'WAITING_FOR_LANDING', 8: 'SECURING_DRONE', 9: 'CHARGING',
    10: 'MAINTAINING', 101: 'ERROR',
}


def best_effort():
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST, depth=1,
        reliability=QoSReliabilityPolicy.BEST_EFFORT,
        durability=QoSDurabilityPolicy.VOLATILE)


def reliable_tl():
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST, depth=1,
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)


class Monitor(Node):
    def __init__(self):
        super().__init__('m3_full_loop_monitor')
        self.t0 = time.time()

        self.drone_trace = []     # (t, state)
        self.box_trace = []       # (t, state_int)
        self.first_on_ground = None
        self.box_gps_seen = False
        self.box_lat = 0.0
        self.box_lon = 0.0
        self.bridge_landed_seen = None

        self.create_subscription(String, '/lander/state', self.on_drone_state, 10)
        self.create_subscription(BoxState, '/box/state', self.on_box_state, 10)
        self.create_subscription(BoxTelemetry, f'/b{BOX_ID}/telemetry', self.on_box_tlm, 10)
        self.create_subscription(DroneTelemetry, f'/d{DRONE_ID}/telemetry',
                                 self.on_drone_tlm, best_effort())
        self.create_subscription(ExtendedState, '/mavros/extended_state',
                                 self.on_ext_state, reliable_tl())

    def el(self):
        return time.time() - self.t0

    def on_drone_state(self, msg):
        if not self.drone_trace or self.drone_trace[-1][1] != msg.data:
            self.drone_trace.append((self.el(), msg.data))
            print(f'[{self.el():7.1f}s] DRONE  -> {msg.data}')

    def on_box_state(self, msg):
        if not self.box_trace or self.box_trace[-1][1] != msg.state:
            name = BOX_NAMES.get(msg.state, f'UNKNOWN({msg.state})')
            self.box_trace.append((self.el(), msg.state))
            print(f'[{self.el():7.1f}s] BOX    -> {name}({msg.state})')

    def on_box_tlm(self, msg):
        self.box_lat = msg.box_info.latitude
        self.box_lon = msg.box_info.longitude
        if not self.box_gps_seen and abs(self.box_lat) > 1e-6:
            self.box_gps_seen = True
            print(f'[{self.el():7.1f}s] BOX GPS valid: '
                  f'lat={self.box_lat:.8f} lon={self.box_lon:.8f}')

    def on_drone_tlm(self, msg):
        if msg.state.landed_state == 1 and self.bridge_landed_seen is None:
            self.bridge_landed_seen = self.el()
            print(f'[{self.el():7.1f}s] BRIDGE -> d{DRONE_ID}/telemetry landed_state=ON_GROUND')

    def on_ext_state(self, msg):
        if msg.landed_state == 1 and self.first_on_ground is None:
            # ignore the pre-takeoff ground state: only count it once airborne
            if any(s in ('START', 'FINAL_APPROACH', 'DESCEND_ABOVE_TARGET')
                   for _, s in self.drone_trace):
                self.first_on_ground = self.el()
                print(f'[{self.el():7.1f}s] MAVROS -> landed_state=ON_GROUND (land detector)')


def t_of_drone(trace, name):
    for t, s in trace:
        if s == name:
            return t
    return None


def t_of_box(trace, val):
    for t, s in trace:
        if s == val:
            return t
    return None


def main():
    rclpy.init()
    node = Monitor()
    print('\n=== 7b full closed-loop monitor (passive) ===')
    print('Listening. Fly the mission, then Ctrl+C for the report.\n')
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    dt = node.drone_trace
    bt = node.box_trace
    dnames = [s for _, s in dt]

    print('\n\n--- DRONE FSM trace ---')
    print(' -> '.join(dnames) if dnames else '(nothing on /lander/state)')
    print('\n--- BOX FSM trace ---')
    print(' -> '.join(f'{BOX_NAMES.get(s, s)}({s})' for _, s in bt) if bt
          else '(nothing on /box/state)')

    results = []

    need_d = ['GOTO_BOX', 'PRELANDING_CHECK', 'WAIT_BOX_READY', 'START']
    idx = [dnames.index(s) for s in need_d if s in dnames]
    ok1 = len(idx) == len(need_d) and idx == sorted(idx)
    results.append(('Drone FSM: GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START',
                    ok1, f'missing: {[s for s in need_d if s not in dnames]}' if not ok1
                    else 'in order'))

    # DONE can last only a few tens of ms (FINAL_APPROACH -> DONE -> IDLE all
    # inside one control tick), and /lander/state publishes at ~10 Hz, so a
    # passive observer can legitimately never sample it. Accept the equivalent
    # evidence: FINAL_APPROACH was reached and the drone ended up back in IDLE,
    # which is only reachable from FINAL_APPROACH via DONE.
    done_ok = ('DONE' in dnames) or ('FINAL_APPROACH' in dnames and dnames[-1] == 'IDLE')
    results.append(('Landing completed (DONE reached; may be too brief to sample)',
                    done_ok,
                    f'trace tail = {" -> ".join(dnames[-3:]) if dnames else "n/a"}'))

    need_b = [0, 6, 7, 8]
    bvals = [s for _, s in bt]
    bidx = [bvals.index(v) for v in need_b if v in bvals]
    ok3 = len(bidx) == len(need_b) and bidx == sorted(bidx)
    results.append(('Box FSM: EMPTY -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING -> SECURING_DRONE',
                    ok3, f'missing: {[BOX_NAMES[v] for v in need_b if v not in bvals]}'
                    if not ok3 else 'in order'))

    t_wait = t_of_drone(dt, 'WAIT_BOX_READY')
    t_prep = t_of_box(bt, 6)
    ok4 = t_wait is not None and t_prep is not None and t_prep >= t_wait - 0.5
    results.append(('Box started preparing AFTER drone entered WAIT_BOX_READY '
                    '(drone caused it, not a manual trigger)',
                    ok4, f'drone WAIT_BOX_READY @{t_wait}s, box PREPARING @{t_prep}s'))

    t_start = t_of_drone(dt, 'START')
    t_ready = t_of_box(bt, 7)
    ok5 = t_start is not None and t_ready is not None and t_start >= t_ready - 0.5
    results.append(('Drone entered START only AFTER box reached WAITING_FOR_LANDING',
                    ok5, f'box READY @{t_ready}s, drone START @{t_start}s'))

    t_sec = t_of_box(bt, 8)
    ok6 = (node.first_on_ground is not None and t_sec is not None
           and t_sec >= node.first_on_ground - 0.5)
    results.append(('Box reached SECURING_DRONE after the real land detector fired',
                    ok6, f'ON_GROUND @{node.first_on_ground}s, SECURING @{t_sec}s'))

    # M3.6: the lifecycle now closes. Before M3.6 the drone never asked to be
    # powered off, so the box sat in SECURING_DRONE and escaped only through
    # its own "drone telemetry went stale" fallback -- it never charged.
    t_charge = t_of_box(bt, 9)
    ok7 = t_charge is not None and t_sec is not None and t_charge >= t_sec
    results.append(('Box reached CHARGING (M3.6: drone requested power off)',
                    ok7,
                    f'SECURING @{t_sec}s, CHARGING @{t_charge}s'
                    if ok7 else
                    f'box never reached CHARGING (last box state '
                    f'{BOX_NAMES.get(bvals[-1], bvals[-1]) if bvals else "n/a"})'))

    results.append(('Box GPS was valid (non-zero) — /gps fixture running',
                    node.box_gps_seen,
                    f'lat={node.box_lat:.8f} lon={node.box_lon:.8f}'))

    print('\n--- criteria ---')
    for name, ok, detail in results:
        print(f'  [{"PASS" if ok else "FAIL"}] {name}\n         {detail}')

    overall = all(ok for _, ok, _ in results)
    print(f'\n=== full closed loop (7c + M3.6): {"PASS" if overall else "FAIL"} ===\n')

    node.destroy_node()
    rclpy.shutdown()
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
