"""MAVROS for SITL, on the SIMULATION clock.

WHY THIS EXISTS
`ros2 launch mavros px4.launch ... use_sim_time:=true` does NOT work. Neither
px4.launch nor the node.launch it includes declares a `use_sim_time` argument
(px4.launch declares exactly nine: fcu_url, gcs_url, tgt_system, tgt_component,
log_output, fcu_protocol, respawn_mavros, namespace, and the two yaml paths it
passes on), so the value is dropped and mavros_node keeps running on the wall
clock.

That failure is silent and it matters. MAVROS stamps
/mavros/local_position/pose with its own clock, while the camera frames come
from the gz bridge stamped with simulation time. The tracker's poseAt() then
finds the two timestamps thousands of seconds apart, trips its clock-domain
guard, and the HUD prints

    UAV ENU: E=.., N=.., U=..  (sync N/A: clock mismatch)

in red -- correct behaviour, but it means the altitude drawn on the frame is
simply the newest pose available rather than the one belonging to that frame.

This file starts the same mavros_node with the same two config files, and adds
use_sim_time as a real node parameter.

USAGE (replaces the `ros2 launch mavros px4.launch ...` terminal):

    ros2 launch precision_landing sitl_mavros.launch.py

Verify it took effect:

    ros2 param get /mavros/mavros_node use_sim_time   # -> Boolean value is: True

Note the node name: mavros_node runs inside the `mavros` namespace and splits
into dozens of plugin nodes, so plain `/mavros` does not exist and querying it
returns "Node not found".

The result that actually matters is on the tracker side, because it measures
the thing rather than its cause:

    ros2 topic echo --once --field data /landing/pose_sync_ms
    # positive milliseconds = one clock domain; -1.0 = still mismatched
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


def generate_launch_description():
    mavros_share = get_package_share_directory('mavros')

    return LaunchDescription([
        DeclareLaunchArgument(
            'fcu_url', default_value='udp://:14540@127.0.0.1:14557'),
        DeclareLaunchArgument('gcs_url', default_value=''),
        DeclareLaunchArgument('tgt_system', default_value='1'),
        DeclareLaunchArgument('tgt_component', default_value='1'),
        DeclareLaunchArgument('fcu_protocol', default_value='v2.0'),
        DeclareLaunchArgument('namespace', default_value='mavros'),

        Node(
            package='mavros',
            executable='mavros_node',
            namespace=LaunchConfiguration('namespace'),
            output='screen',
            parameters=[
                # Same two files px4.launch feeds node.launch.
                os.path.join(mavros_share, 'launch', 'px4_pluginlists.yaml'),
                os.path.join(mavros_share, 'launch', 'px4_config.yaml'),
                {
                    'fcu_url': LaunchConfiguration('fcu_url'),
                    'gcs_url': LaunchConfiguration('gcs_url'),
                    'tgt_system': LaunchConfiguration('tgt_system'),
                    'tgt_component': LaunchConfiguration('tgt_component'),
                    'fcu_protocol': LaunchConfiguration('fcu_protocol'),
                    # The whole point of this file.
                    'use_sim_time': True,
                },
            ],
        ),
    ])
