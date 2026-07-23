"""Everything on the box side of the drone-in-a-box loop, in one terminal.

Replaces three separate `ros2 run` terminals:

    box_hardware_adapter_node        box services  <-> ros2_control joints
    box_state_manager_node           the box FSM
    mavros_to_dib_telemetry          MAVROS       -> d<id>/telemetry

PRODUCT ONLY -- nothing here is test scaffolding, so this launch is what runs
on real hardware unchanged. The SITL fixtures it used to start (the box GPS
publisher) now live in docs/m3_box_handshake_test/sitl_fixtures.launch.py,
alongside the loop monitor, because both are test tooling under a gitignored
directory and have no place in the shipped product.

None of them need a particular start order: services are waited on lazily and
every subscription is fire-and-forget, so a flat launch is enough.

    ros2 launch precision_landing dib_bringup.launch.py

With PX4 (T1), the box spawn (T2), the tracker (T3) and MAVROS (T4) this brings
the whole system down to five terminals instead of nine.

WHAT IS DELIBERATELY NOT HERE
- PX4 SITL: needs its own `pxh>` prompt to fly from.
- box_spawn_only.launch.py: belongs to box_simulation and must start after
  PX4's Gazebo server is up.
- sitl_precland.launch.py / sitl_mavros.launch.py: kept separate because their
  logs are the ones actually worth reading during a landing.
- The SITL fixtures: see above.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


BOX_MANAGER_PARAMS = os.path.join(
    os.path.expanduser('~'), 'PX4', 'examples', 'box_manager', 'config',
    'box_state_manager.yaml')


def generate_launch_description():
    drone_id = LaunchConfiguration('drone_id')

    actions = [
        DeclareLaunchArgument('drone_id', default_value='1'),

        Node(
            package='box_hardware_adapter',
            executable='box_hardware_adapter_node',
            output='screen',
        ),
        Node(
            package='box_manager',
            executable='box_state_manager_node',
            output='screen',
            parameters=[BOX_MANAGER_PARAMS],
        ),
        Node(
            package='precision_landing',
            executable='mavros_to_dib_telemetry',
            output='screen',
            parameters=[{'drone_id': drone_id}],
        ),
    ]

    return LaunchDescription(actions)
