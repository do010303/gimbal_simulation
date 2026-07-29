
# Box Manager

This software package contains the program modules of the box, responsible for coordinating drone takeoff and landing, receiving commands from the server, and creating flight schedules stored on the box.  
It includes 2 nodes:

- `box_state_manager_node`  
- `scheduler_node`  
However, the scheduler_node is not used in this phase.

`preparing_state_manager` and `securing_state_manager` are part of `box_state_manager`.

---

## box_state_manager Node

### Subscriptions

| Topic | Type | Description |
|-------|------|-------------|
| `env/outside/wind` | `dib_msgs/msg/WindSensor` | Wind speed |
| `system1/temperature1` | `dib_msgs/msg/Temperature` | Internal temperature of the box |
| `env/outside/temperature` | `dib_msgs/msg/Temperature` | Ambient temperature |
| `system1/humidity1` | `dib_msgs/msg/Humidity` | Internal humidity of the box |
| `env/outside/humidity` | `dib_msgs/msg/Humidity` | External humidity |
| `env/outside/rain` | `dib_msgs/msg/Rain` | Rain detection outside |
| `/lid/status` | `dib_msgs/msg/LidStatus` | Lid status |
| `/clamp/status` | `dib_msgs/msg/ClampStatus` | Clamp status |
| `/dock/charge/status` | `dib_msgs/msg/ChargeStatus` | Charging information (voltage, current, charging state) |
| `gps` | `sensor_msgs/msg/NavSatFix` | GPS antenna coordinates |
| `rtk_info` | `dib_msgs/msg/RTKInfo` | RTK information |
| `/system1/power/status` | `dib_msgs/msg/PowerStatus` | Power status |
| `/drone_id` | `std_msgs/msg/UInt32` | Drone ID |

### Publishers

| Topic | Description |
|-------|-------------|
| `/box_id/telemetry` | Telemetry data of the box |
| `/box/state` | Current state of the box |

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/box_id/cmd` | `dib_msgs/srv/BoxCmd` | Command interface for the box |
| `/box/mission_upload` | `dib_msgs/srv/MissionUpload` | Upload mission to the box |

### Client Services

| Service | Type | Description |
|---------|------|-------------|
| `/lid/cmd` | `dib_msgs/srv/LidCmd` | Command for the lid |
| `/dock/power_button/cmd` | `dib_msgs/srv/PowerButtonCmd` | Command for dock power button |
| `/dock/charge/cmd` | `dib_msgs/srv/ChargeCmd` | Command for drone charging |
| `/dock/cooling_battery/cmd` | `dib_msgs/srv/CoolingCmd` | Command for battery cooling system |
| `/clamp/cmd` | `dib_msgs/msg/ClampCmd` | Command for clamps |

---

## scheduler Node

### Services

| Service | Type | Description |
|---------|------|-------------|
| `/mission_schedule/cmd` | `dib_msgs/srv/MissionScheduleCmd` | Command to schedule missions |
| `/box/state` | `dib_msgs/srv/BoxState` | Get current state of the box |

### Client Services

| Service | Type | Description |
|---------|------|-------------|
| `/box/mission_upload` | `dib_msgs/srv/MissionUpload` | Upload mission to the box |

---

## Installation

The package requires `dib_msgs`:

```bash
mkdir -p ~/ws/src
cd ~/ws/src
git clone -b dev https://gitlab.phenikaax.com/dib-box/embedded_pc/dib_msgs.git
git clone -b dev https://gitlab.phenikaax.com/dib-box/embedded_pc/box_manager.git
git clone -b station git@gitlab.phenikaax.com:dib-box/embedded_pc/base_rtk.git
cd ~/ws
colcon build
```

Check if the build was successful:

```bash
source ~/ws/install/setup.bash
ros2 run box_manager box_manager_node
```

Repositories:  
- https://gitlab.phenikaax.com/dib-box/embedded_pc/dib_msgs.git  
- https://gitlab.phenikaax.com/dib-box/embedded_pc/box_manager.git  

---

## Configuration

On new devices, configuration must be done in the `box_state_manager.yaml` file:

- `box_id`: ID of the box  
- `pos_clamp_h_close`: Closed position of the horizontal clamp  
- `pos_clamp_v_close`: Closed position of the vertical clamp  
- `x_anten_gps_offset`: X coordinate of the landing pad center relative to GPS antenna origin (X axis points to the drone’s nose)  
- `y_anten_gps_offset`: Y coordinate of the landing pad center relative to GPS antenna origin (Y axis points from right wing to left wing)  
- `z_anten_gps_offset`: Z coordinate of the landing pad center relative to GPS antenna origin (Z axis points upwards)  
- `mission_schedule_folder_path`: path to schedule storage folder (using in scheduler_node)

## Launch 
```
source ~/ws/install/setup.bash
ros2 launch box_manager station_manager.launch
```
