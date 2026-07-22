# M3.5: spawn the box into an ALREADY RUNNING Gazebo server (PX4 SITL's),
# instead of starting a private `-r empty.sdf` world like box.launch.py does.
#
# `ros_gz_sim create` talks to the gz transport service of whatever server is
# up, so it is not tied to the world box.launch.py used to launch. Dropping the
# `gazebo` action is all that is needed to put the box in PX4's world.
#
# box.launch.py is deliberately left untouched so the standalone M2 6a test
# stays reproducible.
#
# PREREQUISITES -- both belong in the terminal that runs `make px4_sitl`, NOT
# in this one. Everything here that depends on the gz server's environment must
# be set on the SERVER's process; this launch file cannot reach it.
#
#   1. source ~/gz_ros2_control_ws/install/setup.bash
#      Otherwise the Harmonic system plugin loads the Fortress hardware plugin
#      through pluginlib and the server segfaults on spawn. See the P1.4 note in
#      docs/M3_5_PLAN.md -- GZ_SIM_SYSTEM_PLUGIN_PATH alone is NOT enough.
#
#   2. export GZ_SIM_RESOURCE_PATH=\
#        $HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share
#      The box's meshes are referenced as model://box_simulation/meshes/... and
#      the marker as model://fractal_aruco_marker/marker.png. The process that
#      resolves those URIs is the gz SERVER, started by PX4. Without this the
#      box spawns headless-correct -- `gz model --list` shows Box, the
#      controllers load, /joint_states works -- but EVERY <visual> fails:
#        [Err] Unable to find file with URI [model://box_simulation/meshes/...]
#        [Err] Failed to load geometry for visual: base_link_visual
#      i.e. an invisible box, which reads as "spawn failed" but is not.
#      PX4 APPENDS to this variable (gz_env.sh.in:19), so exporting it first is
#      safe; PX4's own models/worlds still get found.
#
# The SetEnvironmentVariable below is kept only for this launch's own children
# (robot_state_publisher / ros_gz_sim create); it does NOT fix the server.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, RegisterEventHandler,
                            SetEnvironmentVariable, TimerAction)
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node

import xacro

# --- Spawn pose -------------------------------------------------------------
# Derived from box.xacro's collision geometry, not guessed. The model is built
# in a rotated frame, so the spawn applies roll = pi/2, which maps
# model (x, y, z) -> world (x, -z, y).
#
#   base_collision      model (0, -0.46647, 0.58282) size (1.04977, 0.63172, 1.13211)
#     -> world z spans -0.78233 .. -0.15061
#   base_collision.000  model (-0.0157, 0.63546, -1.38812) size (0.72424, 2.80801, 0.36035)
#     (the GPS mast) -> world z spans -0.76854 .. 2.03947
#
# Lowest point is -0.78233, so that is the lift needed to stand on the ground.
# box.launch.py uses 1.0, which leaves the box floating ~0.22 m.
SPAWN_ROLL = 1.5708
SPAWN_Z = 0.78233

# Anywhere except the PX4 spawn origin, and close enough to be in Gazebo's
# default camera view on startup (3.20 m from origin).
SPAWN_X = 2.5
SPAWN_Y = -2.0

# --- Marker pose ------------------------------------------------------------
# The marker is spawned as its OWN SDF model (dib_box_marker) rather than being
# part of box.xacro. That is not a stylistic choice -- see the long comment in
# Tools/simulation/gz/models/dib_box_marker/model.sdf: a <visual> placed inside
# <gazebo reference="base_link"> gets merged into the link's existing visual and
# silently discarded, and URDF cannot express <plane> or a PBR albedo_map
# anyway.
#
# Position is DERIVED from the box spawn above so the two cannot drift apart.
# The marker sits at model (0.0129, -0.1456, 0.5896) -- the centre of the
# landing surface, plus 5 mm along model y to clear the mesh. Applying the same
# roll = pi/2 mapping model (x, y, z) -> world (x, -z, y):
MARKER_X = SPAWN_X + 0.0129     # 2.5129
MARKER_Y = SPAWN_Y - 0.5896     # -2.5896
MARKER_Z = SPAWN_Z - 0.1456     # 0.63673
# Spawned unrotated: the model's plane normal is already +z, i.e. facing up at
# the descending drone. Keep these three numbers in sync with PAD_EAST/PAD_NORTH
# in docs/m3_box_handshake_test/box_gps_publisher.py.


def generate_launch_description():
    pkg_box_sim = get_package_share_directory('box_simulation')
    src_dir = os.path.abspath(os.path.join(pkg_box_sim, '..'))

    # marker.png lives in the PX4 gz model tree; the box's own models dir holds
    # its meshes. Both must be resolvable by the running gz server.
    px4_models = os.path.join(
        os.path.expanduser('~'), 'PX4', 'Tools', 'simulation', 'gz', 'models')

    set_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=[src_dir, ':', pkg_box_sim, ':', px4_models, ':',
               os.environ.get('GZ_SIM_RESOURCE_PATH', '')]
    )

    args = [
        DeclareLaunchArgument('x', default_value=str(SPAWN_X)),
        DeclareLaunchArgument('y', default_value=str(SPAWN_Y)),
        DeclareLaunchArgument('z', default_value=str(SPAWN_Z)),
        DeclareLaunchArgument('R', default_value=str(SPAWN_ROLL)),
        DeclareLaunchArgument('Y_yaw', default_value='0.0'),
    ]

    xacro_file = os.path.join(pkg_box_sim, 'urdf', 'box.xacro')
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
                   '-x', LaunchConfiguration('x'),
                   '-y', LaunchConfiguration('y'),
                   '-z', LaunchConfiguration('z'),
                   '-R', LaunchConfiguration('R'),
                   '-P', '0.0',
                   '-Y', LaunchConfiguration('Y_yaw')],
        output='screen'
    )

    spawn_marker = Node(
        package='ros_gz_sim',
        executable='create',
        name='create_marker',
        arguments=['-file', 'model://dib_box_marker',
                   '-name', 'dib_box_marker',
                   '-x', str(MARKER_X),
                   '-y', str(MARKER_Y),
                   '-z', str(MARKER_Z)],
        output='screen'
    )

    # Loading the controllers is delayed, and each controller gets its OWN
    # process. Both details matter and both were learned the hard way:
    #
    # 1. THE DELAY. The controller_manager lives inside the gz plugin and only
    #    starts once the box model is spawned. Firing load_controller at it
    #    immediately caught it 0.23 s into its own initialisation, and the reply
    #    then took 15.2 s to come back:
    #        667.76  gz_ros2_control: Loading controller_manager
    #        667.99  controller_manager: Loading controller 'joint_state_broadcaster'
    #        683.16  controller_manager: (retry) already loaded
    #    Both `ros2 control load_controller` and `spawner` hard-code a 10 s
    #    SERVICE-CALL timeout in Humble, so they give up, retry, and the retry
    #    fails with "already loaded" even though the load actually succeeded.
    #    NOTE: spawner's --controller-manager-timeout does NOT help -- it bounds
    #    waiting for the service to APPEAR, not the call itself.
    #    The cold start is paid once; afterwards each load takes well under 1 s.
    #
    # 2. ONE PROCESS PER CONTROLLER. A single spawner listing all four means the
    #    first failure aborts the rest -- exactly what happened when
    #    joint_state_broadcaster tripped the timeout and the other three were
    #    never attempted. Independent processes degrade one-at-a-time instead.
    #
    # If a controller still ends up 'unconfigured', it IS loaded -- the load
    # succeeded and only the activation half was lost to the timeout. Finish it
    # by hand, in TWO steps (unconfigured -> active is not a legal single
    # transition; asking for it fails with "cannot activate ... from its
    # current state unconfigured"):
    #     ros2 control set_controller_state <name> configure
    #     ros2 control set_controller_state <name> active
    CONTROLLER_LOAD_DELAY_S = 20.0

    def spawner(name):
        return Node(
            package='controller_manager',
            executable='spawner',
            name=f'spawner_{name}',
            arguments=[name, '--controller-manager-timeout', '120'],
            output='screen',
        )

    load_controllers = TimerAction(
        period=CONTROLLER_LOAD_DELAY_S,
        actions=[
            spawner('joint_state_broadcaster'),
            spawner('joint_clamp_h_controller'),
            spawner('joint_clamp_v_controller'),
            spawner('joint_lid_controller'),
        ],
    )

    return LaunchDescription(args + [
        set_resource_path,
        RegisterEventHandler(event_handler=OnProcessExit(
            target_action=spawn_entity,
            on_exit=[spawn_marker, load_controllers])),
        node_robot_state_publisher,
        spawn_entity,
    ])
