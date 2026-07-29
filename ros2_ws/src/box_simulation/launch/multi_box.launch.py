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
from launch_ros.actions import PushRosNamespace


from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, RegisterEventHandler,TimerAction
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node

from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument

import xacro


def generate_launch_description():
    gazebo = IncludeLaunchDescription(
                PythonLaunchDescriptionSource([os.path.join(
                    get_package_share_directory('gazebo_ros'), 'launch'), '/gazebo.launch.py']),
             )

    box_simulation_path = os.path.join(
        get_package_share_directory('box_simulation'))

    xacro_file = os.path.join(box_simulation_path, 'urdf','box.xacro')
    
    name_space_arg = DeclareLaunchArgument('name_space', default_value='robot1', description='Namespace of robot')

    doc = xacro.parse(open(xacro_file))
    doc2 = xacro.parse(open(xacro_file))
    xacro.process_doc(doc,mappings={
            "name_space": LaunchConfiguration("name_space")})
    params = {'robot_description': doc.toxml()}
    # xacro.process_doc(doc,mappings={'name_space': 'robot2'})
    # params2 = {'robot_description': doc.toxml()}
    
    node_robot_state_publisher = Node(
        name='robot_state_publisher',
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params],namespace='robot1')

    node_robot_state_publisher2 = Node(
        name='robot_state_publisher2',
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[params],namespace='robot2'
    )

    spawn_entity = Node(package='gazebo_ros', executable='spawn_entity.py',
                        arguments=['-topic', '/robot1/robot_description',
                                   '-entity', 'Box1',
                                   '-x', '3.0', '-y', '2.0', '-z', '1.0',
                                   '-R', '1.57', '-P', '0.0', '-Y', '0',
                                   ],
                        output='screen',
                        name='spawn_entity',)
    
    spawn_entity2 = Node(package='gazebo_ros', executable='spawn_entity.py',
                        arguments=['-topic', '/robot2/robot_description',
                                   '-entity', 'Box2',
                                   '-x', '0.0', '-y', '0.0', '-z', '1.0',
                                   '-R', '1.57', '-P', '0.0', '-Y', '0',
                                   ],
                        output='screen',
                        name='spawn_entity2',)
    

    # load_joint_state_controller = ExecuteProcess(
    #     cmd=['ros2 service call /robot1/controller_manager/load_controller controller_manager_msgs/srv/LoadController "{name: \'joint_state_broadcaster\'}"'],
    #     output='screen'
    # )

    # load_joint_clamp_h_controller = ExecuteProcess(
    #     cmd=['ros2 service call /robot1/controller_manager/load_controller controller_manager_msgs/srv/LoadController "{name: \'joint_clamp_h_controller\'}"'],
    #     output='screen',
    #     # additional_env={'ROS_NAMESPACE': 'robot1'}
    # )

    # load_joint_clamp_v_controller = ExecuteProcess(
    #     cmd=['ros2 service call /robot1/controller_manager/load_controller controller_manager_msgs/srv/LoadController "{name: \'joint_clamp_v_controller\'}"'],
    #     output='screen'
    # )

    # load_joint_lid_controller = ExecuteProcess(
    #     cmd=['ros2 service call /robot1/controller_manager/load_controller controller_manager_msgs/srv/LoadController "{name: \'joint_lid_controller\'}"'],
    #     output='screen'
    # )

    # load_controller = ExecuteProcess(
    #     cmd=['ros2', 'service', 'call', 
    #          '/robot1/controller_manager/load_controller', 
    #          'controller_manager_msgs/srv/LoadController', 
    #          '{name: \'joint_clamp_h_controller\'}'],
    #     # output='screen'
    # )

    return LaunchDescription([
        # PushRosNamespace('robot1'),
        # RegisterEventHandler(
        #     event_handler=OnProcessExit(
        #         target_action=spawn_entity,
        #         on_exit=[load_joint_state_controller],
        #     )
        # ),
        # RegisterEventHandler(
        #     event_handler=OnProcessExit(
        #         target_action=load_joint_state_controller,
        #         on_exit=[load_joint_clamp_h_controller],
        #     )
        # ),
        # RegisterEventHandler(
        #     event_handler=OnProcessExit(
        #         target_action=load_joint_state_controller,
        #         on_exit=[load_joint_clamp_v_controller],
        #     )
        # ),
        # RegisterEventHandler(
        #     event_handler=OnProcessExit(
        #         target_action=load_joint_state_controller,
        #         on_exit=[load_joint_lid_controller],
        #     )
        # ),
        # load_controller,
        gazebo,
        # node_robot_state_publisher,
        node_robot_state_publisher2,
        # spawn_entity,
        spawn_entity2,
        # gazebo_ros2_control,
        # TimerAction(period=5.0, actions=[load_controller]) 
    ])