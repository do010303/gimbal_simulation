"""SITL-only fixtures. NOT part of the product.

These stand in for hardware that exists on the real box but has no equivalent
in simulation. They live under docs/ (gitignored) on purpose: dib_bringup.launch.py
must stay runnable on real hardware with no flags to remember, so anything that
only makes sense in SITL is started from here instead.

    ros2 launch precision_landing dib_bringup.launch.py     # product
    python3 docs/m3_box_handshake_test/sitl_fixtures.launch.py   # this file

Or, since it is a plain launch file:

    ros2 launch $PWD/docs/m3_box_handshake_test/sitl_fixtures.launch.py

WHAT IS FAKED AND WHY

box_gps_publisher
    box_state_manager reads the box position from a `gps` topic
    (sensor_msgs/NavSatFix, box_state_manager.cpp:68,187-194). In SITL nothing
    publishes it -- box_simulation's navsat sensor has no ros_gz_bridge. Left
    unfixed, box_info.latitude/longitude stay 0, st_goto_box() computes a
    setpoint thousands of kilometres away, and the drone flies off. That is a
    hard blocker for the closed-loop test, not a cosmetic gap.

On real hardware the box has a real GPS receiver publishing that topic, so
none of this is needed -- which is exactly why it must not be in the product
launch.
"""

import os

from launch import LaunchDescription
from launch.actions import ExecuteProcess


_HERE = os.path.dirname(os.path.abspath(__file__))
GPS_FIXTURE = os.path.join(_HERE, 'box_gps_publisher.py')


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(
            cmd=['python3', GPS_FIXTURE],
            output='screen',
        ),
    ])
