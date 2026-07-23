"""M2 combined test launch: box_simulation (Gazebo) + adapter + box_manager.

Brings up, in one command, the full box-side ROS graph so box_manager can drive
real Gazebo lid/clamp hardware through box_hardware_adapter:

    box_simulation/box.launch.py   -> Gazebo world + box model + JTCs + /joint_states
    box_hardware_adapter_node      -> dib_msgs <-> JointTrajectory bridge
    box_state_manager_node         -> the box FSM under test

Flat actions (no event-handler ordering): all three tolerate their peers
starting late (box_manager lazily wait_for_service's the adapter; the adapter's
pubs/subs are fire-and-forget).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    box_sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('box_simulation'),
                'launch', 'box.launch.py'))
    )

    adapter_config = os.path.join(
        get_package_share_directory('box_hardware_adapter'),
        'config', 'box_hardware_adapter.yaml')
    adapter_node = Node(
        package='box_hardware_adapter',
        executable='box_hardware_adapter_node',
        name='box_hardware_adapter',
        output='screen',
        parameters=[adapter_config],
    )

    box_manager_config = os.path.join(
        get_package_share_directory('box_manager'),
        'config', 'box_state_manager.yaml')
    box_manager_node = Node(
        package='box_manager',
        executable='box_state_manager_node',
        name='box_state_manager',
        output='screen',
        parameters=[box_manager_config],
    )

    return LaunchDescription([
        box_sim_launch,
        adapter_node,
        box_manager_node,
    ])
