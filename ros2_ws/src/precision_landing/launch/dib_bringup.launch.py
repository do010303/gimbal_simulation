"""The box-side of the drone-in-a-box loop, in one terminal.

    box_hardware_adapter_node        box services  <-> ros2_control joints
    box_state_manager_node           the box FSM
    mavros_to_dib_telemetry          MAVROS       -> d<id>/telemetry   (see below)

    ros2 launch precision_landing dib_bringup.launch.py

WHERE mavros_to_dib_telemetry BELONGS
It reads MAVROS, so on real hardware it runs on the DRONE's onboard computer, not
on the box. It is bundled here only for the single-domain M1-M3 convenience. From
M4 the box and the drone sit on separate ROS_DOMAIN_IDs (bridged by DDS-Router),
and ROS_DOMAIN_ID is per-process -- so the box-side launch must NOT start a
drone-side node. Use the argument:

    include_telemetry_bridge:=true   (default) -- M1-M3, single domain, all here
    include_telemetry_bridge:=false            -- M4 box side; run the bridge on
                                                  the drone domain instead:
        ros2 run precision_landing mavros_to_dib_telemetry --ros-args -p drone_id:=1

None of these need a particular start order: services are waited on lazily and
every subscription is fire-and-forget, so a flat launch is enough. This launch is
PRODUCT ONLY -- SITL fixtures (the box GPS publisher) live in
docs/m3_box_handshake_test/sitl_fixtures.launch.py.

WHAT IS DELIBERATELY NOT HERE
- PX4 SITL: needs its own `pxh>` prompt to fly from.
- box_spawn_only.launch.py: belongs to box_simulation, must start after gz is up.
- sitl_precland.launch.py / sitl_mavros.launch.py: their logs are worth reading
  on their own during a landing.
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


# Resolve from the installed box_manager package share, not a hard-coded home
# path -- box_manager is vendored into this workspace (ros2_ws/src/box_manager)
# and its CMakeLists installs config/ to share/box_manager/, so this works from
# any clone. The old '~/PX4/examples/box_manager/...' path broke on every other
# machine.
BOX_MANAGER_PARAMS = os.path.join(
    get_package_share_directory('box_manager'), 'config',
    'box_state_manager.yaml')


def generate_launch_description():
    drone_id = LaunchConfiguration('drone_id')

    actions = [
        DeclareLaunchArgument('drone_id', default_value='1'),
        DeclareLaunchArgument(
            'include_telemetry_bridge', default_value='true',
            description='Start mavros_to_dib_telemetry here. Set false on the M4 '
                        'box domain and run the bridge on the drone domain.'),

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
            condition=IfCondition(LaunchConfiguration('include_telemetry_bridge')),
        ),
    ]

    return LaunchDescription(actions)
