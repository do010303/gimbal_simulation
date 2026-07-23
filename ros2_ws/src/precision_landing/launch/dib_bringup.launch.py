"""Everything on the box side of the drone-in-a-box loop, in one terminal.

Replaces four separate `ros2 run` terminals:

    box_hardware_adapter_node        box services  <-> ros2_control joints
    box_state_manager_node           the box FSM
    box_gps_publisher                SITL fixture: box position on /gps
    mavros_to_dib_telemetry          MAVROS       -> d<id>/telemetry

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

box_gps_publisher is test tooling under docs/, which is gitignored. If it is
missing this launch still starts, and the box simply reports latitude 0 --
see the `box_gps_publisher` note in README section 4.7 for why that matters.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


# docs/ is gitignored test tooling, so reference it by path rather than by
# package share.
_REPO = os.path.join(
    os.path.expanduser('~'), 'PX4', 'examples', 'SITL_PrecisionLanding')
GPS_FIXTURE = os.path.join(
    _REPO, 'docs', 'm3_box_handshake_test', 'box_gps_publisher.py')

BOX_MANAGER_PARAMS = os.path.join(
    os.path.expanduser('~'), 'PX4', 'examples', 'box_manager', 'config',
    'box_state_manager.yaml')


def generate_launch_description():
    drone_id = LaunchConfiguration('drone_id')
    use_gps_fixture = LaunchConfiguration('use_gps_fixture')

    actions = [
        DeclareLaunchArgument('drone_id', default_value='1'),
        DeclareLaunchArgument(
            'use_gps_fixture', default_value='true',
            description='Publish the box position on /gps (SITL only; on real '
                        'hardware the box has a real GPS receiver).'),

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

    if os.path.exists(GPS_FIXTURE):
        actions.append(
            ExecuteProcess(
                cmd=['python3', GPS_FIXTURE],
                output='screen',
                condition=IfCondition(use_gps_fixture),
            ))
    else:
        actions.append(LogInfo(msg=(
            'box_gps_publisher not found at ' + GPS_FIXTURE +
            ' -- the box will report latitude 0 and the drone will fly to a '
            'setpoint thousands of km away. See README section 4.7.')))

    return LaunchDescription(actions)
