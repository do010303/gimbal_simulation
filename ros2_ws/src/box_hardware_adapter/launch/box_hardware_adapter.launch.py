import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    adapter_config = os.path.join(
        get_package_share_directory('box_hardware_adapter'),
        'config',
        'box_hardware_adapter.yaml')

    adapter_node = Node(
        package='box_hardware_adapter',
        executable='box_hardware_adapter_node',
        name='box_hardware_adapter',
        output='screen',
        parameters=[adapter_config],
    )

    return LaunchDescription([adapter_node])
