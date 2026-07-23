# box_hardware_adapter

SITL bridge between `box_manager` (which speaks the `dib_msgs` service/topic
contract) and `box_simulation` (which only exposes raw `ros2_control`
`JointTrajectory` topics + `/joint_states`). It stands in for the real box's
embedded hardware layer.

```
box_manager  ──dib_msgs srv/msg──▶  box_hardware_adapter  ──JointTrajectory──▶  box_simulation (Gazebo)
             ◀──status topics────                         ◀───/joint_states───
```

## Interfaces

Serves (adapter is the **server**, box_manager the client):

| Service | Type | Action |
|---|---|---|
| `/lid/cmd` | `dib_msgs/srv/LidCmd` | `command` 1=open/0=close → lid JointTrajectory |
| `/clamp/cmd` | `dib_msgs/srv/ClampCmd` | `clamp_select` 1=H/2=V/3=both → clamp JointTrajectory |
| `/dock/power_button/cmd` | `dib_msgs/srv/PowerButtonCmd` | stub, instant success |
| `/dock/charge/cmd` | `dib_msgs/srv/ChargeCmd` | stub, updates fixed charge status |
| `/dock/cooling_battery/cmd` | `dib_msgs/srv/CoolingCmd` | stub, updates cooling status |

Publishes (box_manager subscribes):

| Topic | Type | Source |
|---|---|---|
| `/lid/status` | `dib_msgs/msg/LidStatus` | derived from `lid_left_joint` in `/joint_states` |
| `/clamp/status` | `dib_msgs/msg/ClampStatus` | derived from `clamp_h_1_joint`/`clamp_v_1_joint` (mm) |
| `/dock/charge/status` | `dib_msgs/msg/ChargeStatus` | stub |
| `/dock/cooling_battery/status` | `dib_msgs/msg/CoolingStatus` | stub |

Drives (adapter is the publisher into box_simulation's JTCs):
`/joint_lid_controller/joint_trajectory`,
`/joint_clamp_h_controller/joint_trajectory`,
`/joint_clamp_v_controller/joint_trajectory`.

## Unit mapping

- **Lid**: `lid_left_joint` is revolute, 0.0 rad = closed .. 1.57 rad = open.
  Reported as `CLOSED`/`OPENED` when within `lid_settle_eps_rad` of an endpoint,
  else `OPENING`/`CLOSING` inferred by comparing to the previous `/joint_states`
  sample (same idiom `box_manager` uses for clamp inference).
- **Clamp**: `clamp_*_1_joint` are prismatic, 0.0 m = open .. 0.2 m = closed.
  `ClampStatus.clamp_h_pos`/`clamp_v_pos` are reported in **millimetres**
  (`round(m * 1000)`, range 0..200). `ClampStatus` has no state enum — box_manager
  infers OPENED/CLOSED itself against its `pos_clamp_h_close`/`pos_clamp_v_close`
  params, which **must** be set to `200` (full-close in mm) in
  `box_state_manager.yaml`.

## Known simplifications (not physics)

- `charge`/`cooling`/`power_button` have no simulated model in `box_simulation`.
  Their command services return instant success and republish a fixed status
  (`v_bat=12.0`, `i_bat=2.0` when charging). Replace `chargeCmdCallback` +
  the stub status timer if believable charge curves are needed later.
- `ClampCmd.mode` is always `0` at every box_manager call site → accepted but
  ignored.

## Run

Standalone (adapter only — assumes box_simulation + box_manager already up):

```bash
ros2 launch box_hardware_adapter box_hardware_adapter.launch.py
```

Full box-side stack (Gazebo + adapter + box_manager) for M2 testing:

```bash
ros2 launch box_hardware_adapter box_full_stack.launch.py
```
