# Copyright 2020 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from ament_index_python.packages import get_package_share_directory


from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node

import xacro


def generate_launch_description():
    pkg_box_sim = get_package_share_directory('box_simulation')
    src_dir = os.path.abspath(os.path.join(pkg_box_sim, '..'))

    set_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=[src_dir, ':', pkg_box_sim, ':', os.environ.get('GZ_SIM_RESOURCE_PATH', '')]
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('ros_gz_sim'), 'launch'), '/gz_sim.launch.py']),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
    )

    gazebo_ros2_control_demos_path = pkg_box_sim

    # M2: the legacy box_management node (+ its config.yaml) was removed. Its
    # role is now split between box_manager (FSM) and box_hardware_adapter
    # (dib_msgs <-> ros2_control bridge), launched separately. See
    # box_hardware_adapter/launch/box_full_stack.launch.py.

    xacro_file = os.path.join(gazebo_ros2_control_demos_path,
                              'urdf',
                              'box.xacro')

    doc = xacro.process_file(xacro_file, mappings={'name_space': ''})
    params = {'robot_description': doc.toxml()}

    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params]
    )

    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description',
                   '-name', 'Box',
                   '-x', '0.0', '-y', '0.0', '-z', '1.0',
                   '-R', '1.57', '-P', '0.0', '-Y', '0'],
        output='screen'
    )
    
    load_joint_state_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active',
             'joint_state_broadcaster'],
        output='screen'
    )

    load_joint_clamp_h_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'joint_clamp_h_controller'],
        output='screen'
    )

    load_joint_clamp_v_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'joint_clamp_v_controller'],
        output='screen'
    )

    load_joint_lid_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active','joint_lid_controller'],
        output='screen'
    )

    return LaunchDescription([
        set_resource_path,
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=spawn_entity,
                on_exit=[load_joint_state_controller],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_joint_state_controller,
                on_exit=[load_joint_clamp_h_controller],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_joint_state_controller,
                on_exit=[load_joint_clamp_v_controller],
            )
        ),
        RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=load_joint_state_controller,
                on_exit=[load_joint_lid_controller],
            )
        ),
        gazebo,
        node_robot_state_publisher,
        spawn_entity,
    ])
