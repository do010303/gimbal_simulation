# M3 test drivers

SITL test tooling for M3 (7a unit test, 7c/M3.6 loop monitor, datum measurement,
GPS fixture). Tracked as part of the M3 deliverable — see `docs/m3.md`. These run
only in SITL; the product launch (`dib_bringup.launch.py`) contains none of them.

## 7a — handshake FSM unit test (`m3_handshake_unit_test.py`)

Proves the two new states (`PRELANDING_CHECK`, `WAIT_BOX_READY`) and the
`BoxLink` service contract **without PX4, Gazebo or MAVROS**. The driver mocks
both sides the controller talks to: the MAVROS topics/services, and the box
(`/b1/telemetry` publisher + `/b1/cmd` service that mirrors
`box_state_manager.cpp`'s accept rules).

Same idea as M2's 6a-unit: isolate the new logic from heavy, flaky infra so a
failure points at the code and nothing else.

Terminal 1 — controller:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
ros2 run precision_landing offboard_precland_controller --ros-args \
  --params-file src/precision_landing/config/offboard_precland_params.yaml
```

Terminal 2 — driver:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/m3_handshake_unit_test.py
```

Pass criteria (all four must pass):
1. FSM trace contains `GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START`
   in order. **This is the test that matters most** — `can_transition()` is a
   strict whitelist, so a forgotten edge blocks the transition *silently* and
   leaves the drone hovering with no error.
2. `REQUEST_LANDING(23)` is sent with `agent_id == 12` (`drone_id*10 + 2`).
3. It is accepted exactly once — `BoxLink::request_landing()` is called every
   tick, so this catches a broken idempotency guard spamming the box.
4. The controller leaves `WAIT_BOX_READY` only *after* the box reports
   `WAITING_FOR_LANDING(7)` — it must not run ahead of the box's lid/clamps.

> The driver parks the drone directly over the box (dx=dy=0) so `GOTO_BOX`
> arrival is immediate. Navigation is M1/M2's business; this test is only about
> the handshake.

## 7b — full closed loop (real PX4 SITL)

Full procedure: M3 section of `../TEST_PLAN_RESULTS.md`. Two support files live
here:

- **`box_gps_publisher.py`** — REQUIRED fixture. `box_state_manager` reads the
  box position from a `gps` topic that nothing publishes in SITL, so
  `box_info.latitude/longitude` stay 0 and `st_goto_box()` commands a setpoint
  thousands of km away. This publishes the real pad coordinates, derived from
  `fractal_aruco_landing.sdf` + the `dib_box_landing_pad` pose.
- **`m3_full_loop_monitor.py`** — PASSIVE observer. Publishes nothing, calls no
  service; it only subscribes. A PASS therefore cannot be an artifact of the
  harness stimulating the system — the lesson from M2's 6b fidelity metric.

Two gotchas that will silently waste a 6-terminal run:
1. `box_id` must be **2** in `offboard_precland_params.yaml` (matching
   `box_state_manager.yaml`). Already fixed; if it regresses to 1 the drone
   skips the whole handshake with no error.
2. `sitl_precland.launch.py` **already starts the controller**. Do not also run
   `ros2 run precision_landing offboard_precland_controller`.
