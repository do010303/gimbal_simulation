# box_simulation
This package contains a simulation of a box using ROS <br>
* Topic:
   - `/joint_lid_controller/joint_trajectory ` : Control lid
   - `/joint_clamp_h_controller/joint_trajectory` : Control horizonal clamp
   - `/joint_clamp_v_controller/joint_trajectory` : Control vertical clamp

## Basic usage of the packages
1. Install dependent packages
```
sudo apt install ros-$ROS_DISTRO-ros2-control ros-$ROS_DISTRO-ros2-controllers ros-$ROS_DISTRO-gazebo-ros2-control
```
2. Clone the packages into your catkin workspace and compile
```
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://gitlab.phenikaax.com/dib-box/embedded_pc/box_simulation.git
cd ..
colcon build
```
3. Run package
```
ros2 launch box_simulation box.launch.py
```
4. If add box to PX4 SIM
```
ros2 launch box_simulation add_box.launch.py
```

## Control box
* Open lid cmd
```
ros2 topic pub /joint_lid_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory "{
joint_names: ['lid_left_joint'],
    points: [
      {
        positions: [1.57],  # Adjust target positions
        velocities: [0.0],  # Optional, can be omitted
        time_from_start: { sec: 10, nanosec: 0 }
      }
    ]
  }" -1
```
* Close lid cmd
```
ros2 topic pub /joint_lid_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory "{
joint_names: ['lid_left_joint'],
    points: [
      {
        positions: [0.0],  # Adjust target positions
        velocities: [0.0],  # Optional, can be omitted
        time_from_start: { sec: 10, nanosec: 0 }
      }
    ]
  }" -1
```
