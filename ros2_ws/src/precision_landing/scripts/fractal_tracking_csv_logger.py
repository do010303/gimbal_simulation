#!/usr/bin/env python3
"""Log Fractal ArUco tracking data to CSV for real camera distance tests."""

import csv
import math
import os
import subprocess
import time
from collections import deque
from datetime import datetime

import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node

from dib_msgs.msg import LandingTarget6D


class FractalTrackingCsvLogger(Node):
    def __init__(self):
        super().__init__('fractal_tracking_csv_logger')

        numeric_descriptor = ParameterDescriptor(dynamic_typing=True)

        self.declare_parameter('target_topic', '/siyi/landing_target')
        self.declare_parameter('output_dir', '~/PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs')
        self.declare_parameter('trial_label', '')
        self.declare_parameter('expected_distance_cm', 0.0, numeric_descriptor)
        self.declare_parameter('config_id', '')
        self.declare_parameter('resolution', '1280x720')
        self.declare_parameter('tag_size_cm', 16.2, numeric_descriptor)
        self.declare_parameter('test_distance_m', 0.0, numeric_descriptor)
        self.declare_parameter('notes', '')
        self.declare_parameter('gpu_percent_override', -1.0, numeric_descriptor)
        self.declare_parameter('flush_every_n', 1)
        self.declare_parameter('stats_window_sec', 2.0, numeric_descriptor)
        self.declare_parameter('gpu_query_interval_sec', 2.0, numeric_descriptor)

        self.target_topic = self.get_parameter('target_topic').value
        output_dir = os.path.expanduser(self.get_parameter('output_dir').value)
        self.trial_label = str(self.get_parameter('trial_label').value).strip()
        self.expected_distance_cm = float(self.get_parameter('expected_distance_cm').value)
        self.config_id = str(self.get_parameter('config_id').value).strip()
        self.resolution = str(self.get_parameter('resolution').value).strip()
        self.tag_size_cm = float(self.get_parameter('tag_size_cm').value)
        self.test_distance_m = float(self.get_parameter('test_distance_m').value)
        self.notes = str(self.get_parameter('notes').value).strip()
        self.gpu_percent_override = float(self.get_parameter('gpu_percent_override').value)
        self.flush_every_n = max(1, int(self.get_parameter('flush_every_n').value))
        self.stats_window_sec = max(0.5, float(self.get_parameter('stats_window_sec').value))
        self.gpu_query_interval_sec = max(0.5, float(self.get_parameter('gpu_query_interval_sec').value))

        os.makedirs(output_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        label = self._sanitize_label(self.trial_label)
        suffix = f'_{label}' if label else ''
        self.csv_path = os.path.join(output_dir, f'fractal_tracking_{stamp}{suffix}.csv')

        self.csv_file = open(self.csv_path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow([
            'config',
            'resolution',
            'tag_size_cm',
            'test_distance_m',
            'cpu_percent',
            'gpu_percent',
            'fps',
            'detection_rate_percent',
            'accuracy_percent',
            'e2e_latency_ms',
            'notes',
            'wall_time_iso',
            'ros_stamp_sec',
            'ros_stamp_nanosec',
            'trial_label',
            'expected_distance_cm',
            'state',
            'state_name',
            'tag_id',
            'x_m',
            'y_m',
            'z_m',
            'distance_m',
            'distance_cm',
            'error_cm',
        ])

        self.sample_count = 0
        self.tracking_count = 0
        self.window_samples = deque()
        self.last_cpu_total = None
        self.last_cpu_idle = None
        self.last_cpu_percent = math.nan
        self.last_gpu_percent = math.nan
        self.last_gpu_query_time = 0.0

        self.sub = self.create_subscription(
            LandingTarget6D,
            self.target_topic,
            self._on_target,
            10,
        )

        self.get_logger().info(
            'Fractal tracking CSV logger started: '
            f'topic={self.target_topic} file={self.csv_path} '
            f'expected_distance_cm={self.expected_distance_cm:.1f} '
            f'config="{self.config_id}" resolution="{self.resolution}" '
            f'tag_size_cm={self.tag_size_cm:.1f} '
            f'trial_label="{self.trial_label}"'
        )

    @staticmethod
    def _sanitize_label(label: str) -> str:
        safe = []
        for char in label:
            if char.isalnum() or char in ('-', '_'):
                safe.append(char)
            else:
                safe.append('_')
        return ''.join(safe).strip('_')

    @staticmethod
    def _state_name(state: int) -> str:
        if state == LandingTarget6D.LOST:
            return 'LOST'
        if state == LandingTarget6D.SEARCHING:
            return 'SEARCHING'
        if state == LandingTarget6D.TRACKING:
            return 'TRACKING'
        return f'UNKNOWN_{state}'

    @staticmethod
    def _read_cpu_totals():
        try:
            with open('/proc/stat', 'r', encoding='utf-8') as stat_file:
                fields = stat_file.readline().split()
        except OSError:
            return None, None

        if not fields or fields[0] != 'cpu':
            return None, None

        values = [int(value) for value in fields[1:]]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)
        return idle, total

    def _sample_cpu_percent(self) -> float:
        idle, total = self._read_cpu_totals()
        if idle is None or total is None:
            return math.nan

        if self.last_cpu_total is None or self.last_cpu_idle is None:
            self.last_cpu_idle = idle
            self.last_cpu_total = total
            return math.nan

        delta_total = total - self.last_cpu_total
        delta_idle = idle - self.last_cpu_idle
        self.last_cpu_idle = idle
        self.last_cpu_total = total

        if delta_total <= 0:
            return self.last_cpu_percent

        self.last_cpu_percent = max(0.0, min(100.0, 100.0 * (1.0 - (delta_idle / delta_total))))
        return self.last_cpu_percent

    def _sample_gpu_percent(self, now_monotonic: float) -> float:
        if self.gpu_percent_override >= 0.0:
            return self.gpu_percent_override

        if now_monotonic - self.last_gpu_query_time < self.gpu_query_interval_sec:
            return self.last_gpu_percent

        self.last_gpu_query_time = now_monotonic

        # 1. Try Jetson-specific sysfs paths
        jetson_gpu_paths = [
            "/sys/devices/gpu.0/load",
            "/sys/class/devfreq/gp10b/device/load",
            "/sys/class/devfreq/17000000.gp10b/device/load",
            "/sys/class/devfreq/gv11b/device/load",
            "/sys/class/devfreq/17000000.gv11b/device/load",
            "/sys/devices/platform/host1x/17000000.gp10b/load",
            "/sys/devices/platform/host1x/17000000.gv11b/load",
        ]
        for path in jetson_gpu_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        val = float(f.read().strip())
                        # On Jetson, load is typically out of 1000 (e.g. 150 = 15%)
                        if val > 100.0:
                            val = val / 10.0
                        self.last_gpu_percent = val
                        return self.last_gpu_percent
                except Exception:
                    pass

        # 2. Try jetson-stats jtop API if installed
        try:
            from jtop import jtop
            with jtop() as jetson:
                if jetson.ok():
                    gpu_stats = jetson.gpu
                    if gpu_stats and 'val' in gpu_stats:
                        self.last_gpu_percent = float(gpu_stats['val'])
                        return self.last_gpu_percent
        except ImportError:
            pass

        # 3. Fallback to nvidia-smi (for standard Linux PCs)
        try:
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=utilization.gpu',
                    '--format=csv,noheader,nounits',
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            if result.returncode == 0:
                first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ''
                self.last_gpu_percent = float(first_line.strip())
                return self.last_gpu_percent
        except (OSError, subprocess.SubprocessError):
            pass

        self.last_gpu_percent = math.nan
        return self.last_gpu_percent

    @staticmethod
    def _format_float(value: float, precision: int = 3, unavailable: str = '') -> str:
        return f'{value:.{precision}f}' if math.isfinite(value) else unavailable

    def _on_target(self, msg: LandingTarget6D) -> None:
        now_monotonic = time.monotonic()
        state_name = self._state_name(msg.state)
        has_tracking_pose = msg.state == LandingTarget6D.TRACKING and msg.tag_id >= 0

        distance_m = math.sqrt(msg.x * msg.x + msg.y * msg.y + msg.z * msg.z) if has_tracking_pose else math.nan
        distance_cm = distance_m * 100.0 if has_tracking_pose else math.nan
        error_cm = distance_cm - self.expected_distance_cm if has_tracking_pose and self.expected_distance_cm > 0.0 else math.nan
        accuracy_percent = (
            max(0.0, 100.0 - (abs(error_cm) / self.expected_distance_cm * 100.0))
            if math.isfinite(error_cm) and self.expected_distance_cm > 0.0
            else math.nan
        )

        stamp_sec = float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) * 1e-9
        now_ros_sec = self.get_clock().now().nanoseconds * 1e-9
        e2e_latency_ms = (now_ros_sec - stamp_sec) * 1000.0 if stamp_sec > 0.0 else math.nan

        self.window_samples.append((now_monotonic, has_tracking_pose))
        while self.window_samples and now_monotonic - self.window_samples[0][0] > self.stats_window_sec:
            self.window_samples.popleft()

        if len(self.window_samples) >= 2:
            elapsed = max(1e-6, self.window_samples[-1][0] - self.window_samples[0][0])
            fps = (len(self.window_samples) - 1) / elapsed
        else:
            fps = math.nan
        detection_rate_percent = (
            100.0 * sum(1 for _, tracked in self.window_samples if tracked) / len(self.window_samples)
            if self.window_samples
            else math.nan
        )

        cpu_percent = self._sample_cpu_percent()
        gpu_percent = self._sample_gpu_percent(now_monotonic)
        reported_test_distance_m = self.test_distance_m if self.test_distance_m > 0.0 else distance_m
        notes = self.notes
        if not math.isfinite(gpu_percent):
            notes = f'{notes}; gpu=N/A(no nvidia-smi)' if notes else 'gpu=N/A(no nvidia-smi)'
        if not math.isfinite(accuracy_percent):
            reason = 'accuracy=N/A(no expected_distance)' if self.expected_distance_cm <= 0.0 else 'accuracy=N/A(no tracking)'
            notes = f'{notes}; {reason}' if notes else reason

        self.writer.writerow([
            self.config_id,
            self.resolution,
            self._format_float(self.tag_size_cm, 3, 'N/A'),
            self._format_float(reported_test_distance_m, 3, 'N/A'),
            self._format_float(cpu_percent, 1, 'N/A'),
            self._format_float(gpu_percent, 1, 'N/A'),
            self._format_float(fps, 2, 'N/A'),
            self._format_float(detection_rate_percent, 1, 'N/A'),
            self._format_float(accuracy_percent, 2, 'N/A'),
            self._format_float(e2e_latency_ms, 2, 'N/A'),
            notes,
            datetime.now().isoformat(timespec='milliseconds'),
            msg.header.stamp.sec,
            msg.header.stamp.nanosec,
            self.trial_label,
            f'{self.expected_distance_cm:.3f}',
            int(msg.state),
            state_name,
            int(msg.tag_id),
            self._format_float(msg.x, 6) if has_tracking_pose else '',
            self._format_float(msg.y, 6) if has_tracking_pose else '',
            self._format_float(msg.z, 6) if has_tracking_pose else '',
            self._format_float(distance_m, 6) if has_tracking_pose else '',
            self._format_float(distance_cm, 3) if has_tracking_pose else '',
            self._format_float(error_cm, 3) if has_tracking_pose and self.expected_distance_cm > 0.0 else '',
        ])

        self.sample_count += 1
        if has_tracking_pose:
            self.tracking_count += 1

        if self.sample_count % self.flush_every_n == 0:
            self.csv_file.flush()

        if self.sample_count % 30 == 0:
            self.get_logger().info(
                f'samples={self.sample_count} tracking={self.tracking_count} '
                f'last_state={state_name} last_distance_cm='
                f'{distance_cm:.1f}' if has_tracking_pose else
                f'samples={self.sample_count} tracking={self.tracking_count} last_state={state_name}'
            )

    def destroy_node(self):
        if not self.csv_file.closed:
            self.csv_file.flush()
            self.csv_file.close()
            self.get_logger().info(f'CSV saved: {self.csv_path}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = FractalTrackingCsvLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
