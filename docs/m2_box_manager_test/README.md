# M2 test drivers

Throwaway SITL test tooling for M2 (gitignored via `docs/*`). Not shipped.

## 6a — real Gazebo lid/clamp movement (`m2_full_stack_test.py`)

### PREREQUISITE (one-time) — gz_ros2_control for Gazebo Harmonic
The apt `ros-humble-gz-ros2-control` is built for Fortress and fails to load in
Harmonic (missing `GzPluginHook`) → no controllers, no `/joint_states`, box is a
static visual. Build it from source for Harmonic once:
```bash
mkdir -p ~/gz_ros2_control_ws/src && cd ~/gz_ros2_control_ws/src
git clone -b humble --depth 1 https://github.com/ros-controls/gz_ros2_control.git
cd ~/gz_ros2_control_ws
export GZ_VERSION=harmonic
colcon build --packages-select gz_ros2_control --cmake-args -DCMAKE_BUILD_TYPE=Release
```
Also required: `box.xacro` plugin name must be `gz_ros2_control` (not
`ign_ros2_control`) — already fixed in this repo.

Terminal 1 — full box-side stack (Gazebo + adapter + box_manager):
```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash          # <-- REQUIRED: Harmonic plugin
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch box_hardware_adapter box_full_stack.launch.py
```
Sanity check (terminal 3): `ros2 control list_controllers` shows 4 controllers
`active`; `ros2 topic echo --once /joint_states` shows 6 joints.

Terminal 2 — driver:
```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m2_box_manager_test/m2_full_stack_test.py
```

> Re-run needs a launch restart: after one cycle the box is CHARGING and refuses
> a new REQUEST_LANDING (FSM only accepts it from EMPTY). Ctrl+C the launch and
> relaunch to reset to EMPTY.

Prints the `/box/state` trace plus hardware observations (lid joint range,
`/lid/status` values seen, clamp mm range, box_info.clamp_state) and a PASS/FAIL
summary. The drone-landed signal is hand-published (M1-style) so the box FSM
reaches SECURING_DRONE; the real MAVROS passthrough is 6b's job.

## 6b — real MAVROS landed passthrough (`m2_telemetry_bridge_test.py`)

Proves box_manager transitions WAITING_FOR_LANDING -> SECURING_DRONE off a REAL
PX4 land-detector signal via the bridge, with NO hand-published DroneTelemetry.
Box hardware here is the M1 mock (no box Gazebo needed — this test is drone-side).

6 terminals (source ROS + ws in each):
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

- **T1** PX4 SITL (keep the `pxh>` shell — you fly from here):
  ```bash
  cd ~/PX4 && make px4_sitl gz_x500
  ```
- **T2** MAVROS:
  ```bash
  ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580
  ```
- **T3** box_state_manager:
  ```bash
  cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
  ros2 run box_manager box_state_manager_node --ros-args \
    --params-file src/box_manager/config/box_state_manager.yaml
  ```
- **T4** mock box hardware (so box FSM can open lid/clamp without box Gazebo):
  ```bash
  python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m1_box_manager_test/mock_hw_stub.py
  ```
- **T5** telemetry bridge:
  ```bash
  ros2 run precision_landing mavros_to_dib_telemetry --ros-args -p drone_id:=1
  ```
- **T6** driver (guides you; trigger + monitor):
  ```bash
  python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m2_box_manager_test/m2_telemetry_bridge_test.py
  ```

The driver prompts you at the right moments to type in the **T1 pxh> shell**:
```
pxh> commander takeoff     # when it says "waiting for drone IN_AIR"
pxh> commander land        # when it says "Now ... commander land"
```

Pass = bridge fidelity (d1/telemetry landed_state always == mavros), box reaches
WAITING_FOR_LANDING while airborne, then auto-transitions to SECURING_DRONE on
touchdown — driver publishes no telemetry itself.
