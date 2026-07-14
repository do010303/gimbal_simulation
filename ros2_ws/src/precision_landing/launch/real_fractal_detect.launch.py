import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory


def _launch_bool(value: str) -> bool:
    return value.lower() in ('1', 'true', 'yes', 'on')


def _maybe_start_mavros(context):
    if not _launch_bool(LaunchConfiguration('enable_mavros').perform(context)):
        return []

    mavros_dir = get_package_share_directory('mavros')
    return [
        IncludeLaunchDescription(
            XMLLaunchDescriptionSource(
                os.path.join(mavros_dir, 'launch', 'px4.launch')
            ),
            launch_arguments={
                'fcu_url': LaunchConfiguration('fcu_url'),
            }.items(),
        )
    ]


def generate_launch_description():
    pkg_share = get_package_share_directory('precision_landing')
    rtsp_params_file = os.path.join(pkg_share, 'config', 'rtsp_publisher_params.yaml')

    # ── Launch Arguments ────────────────────────────────────────────

    marker_configuration_arg = DeclareLaunchArgument(
        'marker_configuration',
        default_value=os.path.join(
            os.path.expanduser('~'),
            'PX4/examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/models/'
            'fractal_aruco_marker/custom_fractal.yml'
        ),
        description='Absolute path to the fractal marker configuration YAML'
    )

    marker_size_arg = DeclareLaunchArgument(
        'marker_size',
        default_value='0.50',
        description='Physical size of outer marker in meters'
    )

    enable_mavros_arg = DeclareLaunchArgument(
        'enable_mavros',
        default_value='true',
        description='Enable MAVROS node (set false if no FCU connected)'
    )

    fcu_url_arg = DeclareLaunchArgument(
        'fcu_url',
        default_value='udp://:14540@127.0.0.1:14580',
        description='MAVROS FCU URL (e.g. /dev/ttyACM0:57600 for USB Pixhawk)'
    )

    enable_csv_logger_arg = DeclareLaunchArgument(
        'enable_csv_logger',
        default_value='false',
        description='Enable CSV logger for real marker distance tests'
    )

    logger_expected_distance_cm_arg = DeclareLaunchArgument(
        'logger_expected_distance_cm',
        default_value='0.0',
        description='Ground-truth marker distance in centimeters for this test sample'
    )

    logger_trial_label_arg = DeclareLaunchArgument(
        'logger_trial_label',
        default_value='',
        description='Short label written into the CSV filename and rows, e.g. 70cm'
    )

    logger_output_dir_arg = DeclareLaunchArgument(
        'logger_output_dir',
        default_value=os.path.join(
            os.path.expanduser('~'),
            'PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs'
        ),
        description='Directory where tracker CSV logs are written'
    )

    logger_config_id_arg = DeclareLaunchArgument(
        'logger_config_id',
        default_value='',
        description='Test config ID written to CSV, e.g. A1, B2, E1'
    )

    logger_resolution_arg = DeclareLaunchArgument(
        'logger_resolution',
        default_value='1280x720',
        description='Camera resolution label written to CSV, e.g. 640x480'
    )

    logger_tag_size_cm_arg = DeclareLaunchArgument(
        'logger_tag_size_cm',
        default_value='16.2',
        description='Outer marker/tag size in centimeters written to CSV'
    )

    logger_test_distance_m_arg = DeclareLaunchArgument(
        'logger_test_distance_m',
        default_value='0.0',
        description='Nominal test distance in meters written to CSV; use 0.0 for continuous sweeps'
    )

    logger_notes_arg = DeclareLaunchArgument(
        'logger_notes',
        default_value='',
        description='Free-form notes written to every CSV row'
    )

    logger_gpu_percent_override_arg = DeclareLaunchArgument(
        'logger_gpu_percent_override',
        default_value='-1.0',
        description='Optional fixed GPU percent written to CSV; -1 uses nvidia-smi when available'
    )

    # ── 1. MAVROS (optional) ────────────────────────────────────────

    mavros_launch = OpaqueFunction(function=_maybe_start_mavros)

    # ── 2. RTSP Camera Publisher ───────────────────────────────────

    rtsp_node = Node(
        package='precision_landing',
        executable='rtsp_publisher',
        name='siyi_rtsp_publisher',
        parameters=[rtsp_params_file],
        output='screen'
    )

    # ── 3. Fractal ArUco Tracker ────────────────────────────────────

    tracker_node = Node(
        package='precision_landing',
        executable='aruco_fractal_tracker',
        name='aruco_fractal_tracker',
        parameters=[{
            'marker_configuration': LaunchConfiguration('marker_configuration'),
            'marker_size': LaunchConfiguration('marker_size'),
            'min_tracking_z': 0.15,
            'max_tracking_z': 20.0,
            'max_pose_jump_m': 2.0,
            'acquire_good_frames': 5,
            'lost_bad_frames': 3,
            'show_latency_overlay': True,
            'latency_warn_ms': 100.0,
            'use_sim_time': False,
            # Camera-to-body sign mapping for real SIYI A8 Mini
            # pointing straight down: camera X = body East, camera Y = body South
            'camera_x_to_body_east_sign': -1.0,
            'camera_y_to_body_north_sign': 1.0,
            # Camera offset from drone center
            'camera_offset_x': 0.0,
            'camera_offset_y': 0.0,
        }],
        remappings=[
            ('image_input_topic', '/siyi/image_raw'),
            ('camera_info_topic', '/siyi/camera_info'),
            ('image_output_topic', '/siyi/fractal_debug'),
            ('poses_output_topic', '/siyi/fractal_pose'),
            ('target_output_topic', '/siyi/landing_target'),
        ],
        output='screen'
    )

    csv_logger_node = Node(
        package='precision_landing',
        executable='fractal_tracking_csv_logger',
        name='fractal_tracking_csv_logger',
        condition=IfCondition(LaunchConfiguration('enable_csv_logger')),
        parameters=[{
            'target_topic': '/siyi/landing_target',
            'expected_distance_cm': LaunchConfiguration('logger_expected_distance_cm'),
            'trial_label': LaunchConfiguration('logger_trial_label'),
            'output_dir': LaunchConfiguration('logger_output_dir'),
            'config_id': LaunchConfiguration('logger_config_id'),
            'resolution': LaunchConfiguration('logger_resolution'),
            'tag_size_cm': LaunchConfiguration('logger_tag_size_cm'),
            'test_distance_m': LaunchConfiguration('logger_test_distance_m'),
            'notes': LaunchConfiguration('logger_notes'),
            'gpu_percent_override': LaunchConfiguration('logger_gpu_percent_override'),
        }],
        output='screen'
    )

    return LaunchDescription([
        marker_configuration_arg,
        marker_size_arg,
        enable_mavros_arg,
        fcu_url_arg,
        enable_csv_logger_arg,
        logger_expected_distance_cm_arg,
        logger_trial_label_arg,
        logger_output_dir_arg,
        logger_config_id_arg,
        logger_resolution_arg,
        logger_tag_size_cm_arg,
        logger_test_distance_m_arg,
        logger_notes_arg,
        logger_gpu_percent_override_arg,
        mavros_launch,
        rtsp_node,
        tracker_node,
        csv_logger_node,
    ])
