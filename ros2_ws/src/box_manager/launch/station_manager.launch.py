#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # -----------------------
    # Launch Arguments
    # -----------------------
    box_manager_config_arg = DeclareLaunchArgument(
        'box_manager_config',
        default_value=PathJoinSubstitution([
            FindPackageShare('box_manager'),
            'config',
            'box_state_manager.yaml'
        ]),
        description='Path to box state manager config file'
    )

    box_id_arg = DeclareLaunchArgument(
        'box_id',
        default_value='1',
        description='Box ID parameter'
    )

    # -----------------------
    # Node: box_state_manager
    # -----------------------
    box_state_manager_node = Node(
        package='box_manager',
        executable='box_state_manager_node',
        name='box_state_manager',
        output='screen',
        parameters=[
            LaunchConfiguration('box_manager_config'),
            {'box_id': LaunchConfiguration('box_id')}
        ],
        arguments=['--ros-args', '--log-level', 'INFO']
    )

    # -----------------------
    # Include base_rtk launch
    # -----------------------
    base_rtk_launch = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('base_rtk'),
                'launch',
                'base_rtk.launch.py'
            ])
        )
    )

    # -----------------------
    # Launch Description
    # -----------------------
    return LaunchDescription([
        box_manager_config_arg,
        box_id_arg,
        box_state_manager_node,
        base_rtk_launch
    ])