#!/usr/bin/env python3
"""
Verify the tracker's overlay pose/image time-sync fix (M3 follow-up).

The bug: the overlay drew `last_uav_pose_` (newest pose available) on an image
whose content was older, so UAV altitude and MARKER DIST in the same picture
came from different instants (observed 0.75 m apart in 7b).

This test feeds the tracker synthetic images whose header.stamp is deliberately
BEHIND the newest pose, and reads the burnt-in "UAV ENU ... U=..." text back out
of /landing/annotated_image via template-free OCR-less checking: we choose pose
altitudes that are far apart and check which one the overlay committed to, by
reading the rendered pixels is impractical -- so instead we rely on the sync
readout the node now prints and on distinguishable altitudes.

Two scenarios:
  A) matched clocks   -> overlay must pick the pose AT the image stamp
  B) mismatched clocks (pose stamps in wall time, image in "sim" time)
     -> overlay must fall back to the newest pose and report "sync N/A"

Because reading text from the image needs OCR, this script instead asserts the
observable side effect that does not need OCR: the annotated image is produced
at all, and the node does not crash / stall under either clock regime. The
altitude actually drawn is verified by eye from the saved PNGs it writes.

Usage:
  ros2 run precision_landing aruco_fractal_tracker --ros-args \
      -p marker_configuration:=<...>/custom_fractal.yml -p marker_size:=0.5 \
      -r image_input_topic:=/gimbal_camera \
      -r camera_info_topic:=/gimbal_camera/camera_info \
      -r image_output_topic:=/landing/annotated_image
  python3 overlay_sync_test.py
"""

import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy
from rclpy.time import Time

from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PoseStamped

W, H = 640, 360

# Altitudes chosen far apart so the drawn value is unambiguous by eye.
ALT_AT_IMAGE_TIME = 9.0     # pose that matches the image stamp
ALT_NEWEST = 2.0            # newest pose, 2 s later

IMAGE_LAG_S = 2.0           # how far the image stamp trails the newest pose


def pose_qos():
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST, depth=1,
        reliability=QoSReliabilityPolicy.BEST_EFFORT,
        durability=QoSDurabilityPolicy.VOLATILE)


class OverlaySyncTest(Node):
    def __init__(self):
        super().__init__('overlay_sync_test')
        self.pub_img = self.create_publisher(Image, '/gimbal_camera', 10)
        self.pub_ci = self.create_publisher(CameraInfo, '/gimbal_camera/camera_info', 10)
        self.pub_pose = self.create_publisher(
            PoseStamped, '/mavros/local_position/pose', pose_qos())
        self.sub_out = self.create_subscription(
            Image, '/landing/annotated_image', self.on_out, 10)
        self.out_count = 0
        self.last_out = None

    def on_out(self, msg):
        self.out_count += 1
        self.last_out = msg

    def make_image(self, stamp):
        m = Image()
        m.header.stamp = stamp
        m.header.frame_id = 'camera_link'
        m.height, m.width = H, W
        m.encoding = 'rgb8'
        m.is_bigendian = 0
        m.step = W * 3
        # mid-grey frame; no marker needed -- the UAV ENU block is drawn
        # regardless of detection.
        m.data = (np.full((H, W, 3), 140, dtype=np.uint8)).tobytes()
        return m

    def make_ci(self, stamp):
        ci = CameraInfo()
        ci.header.stamp = stamp
        ci.header.frame_id = 'camera_link'
        ci.width, ci.height = W, H
        f = 500.0
        ci.k = [f, 0.0, W / 2.0, 0.0, f, H / 2.0, 0.0, 0.0, 1.0]
        ci.p = [f, 0.0, W / 2.0, 0.0, 0.0, f, H / 2.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ci.d = [0.0] * 5
        ci.distortion_model = 'plumb_bob'
        return ci

    def make_pose(self, stamp, z):
        p = PoseStamped()
        p.header.stamp = stamp
        p.header.frame_id = 'map'
        p.pose.position.x = 4.0
        p.pose.position.y = -3.5
        p.pose.position.z = z
        p.pose.orientation.w = 1.0
        return p

    def run_case(self, name, pose_base_s, image_base_s):
        """pose stamps around pose_base_s; image stamped image_base_s."""
        print(f'\n--- {name} ---')
        self.out_count = 0

        def T(sec):
            return Time(seconds=int(sec), nanoseconds=int((sec % 1) * 1e9)).to_msg()

        # Older pose that MATCHES the image instant.
        self.pub_pose.publish(self.make_pose(T(pose_base_s), ALT_AT_IMAGE_TIME))
        for _ in range(20):
            rclpy.spin_once(self, timeout_sec=0.02)
        # Newest pose, IMAGE_LAG_S later and much lower.
        self.pub_pose.publish(
            self.make_pose(T(pose_base_s + IMAGE_LAG_S), ALT_NEWEST))
        for _ in range(20):
            rclpy.spin_once(self, timeout_sec=0.02)

        # Image carrying the OLD instant.
        for _ in range(5):
            self.pub_ci.publish(self.make_ci(T(image_base_s)))
            self.pub_img.publish(self.make_image(T(image_base_s)))
            for _ in range(15):
                rclpy.spin_once(self, timeout_sec=0.02)

        deadline = time.time() + 3.0
        while self.out_count == 0 and time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

        print(f'  annotated frames received: {self.out_count}')
        if self.last_out is not None:
            path = f'/tmp/claude-1000/overlay_{name.replace(" ", "_")}.png'
            try:
                import cv2
                arr = np.frombuffer(self.last_out.data, dtype=np.uint8).reshape(
                    self.last_out.height, self.last_out.width, 3)
                cv2.imwrite(path, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
                print(f'  saved: {path}')
            except Exception as exc:  # pragma: no cover
                print(f'  (could not save png: {exc})')
        return self.out_count > 0


def main():
    rclpy.init()
    node = OverlaySyncTest()
    print('=== overlay pose/image sync test ===')
    print('Waiting for the tracker to subscribe...')
    deadline = time.time() + 10.0
    while time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if node.pub_img.get_subscription_count() > 0:
            break
    if node.pub_img.get_subscription_count() == 0:
        print('FAIL: tracker is not subscribed to /gimbal_camera')
        return 1

    # A) matched clocks: image stamp equals the older pose stamp.
    ok_a = node.run_case('A matched clocks', pose_base_s=1000.0, image_base_s=1000.0)
    print(f'  expect drawn U = {ALT_AT_IMAGE_TIME:.1f} (pose at image time), '
          f'sync ~0ms')

    # B) mismatched clocks: poses in wall time, image in sim time.
    ok_b = node.run_case('B clock mismatch', pose_base_s=1.78e9, image_base_s=1000.0)
    print(f'  expect drawn U = {ALT_NEWEST:.1f} (newest pose fallback), '
          f'sync "N/A: clock mismatch"')

    print('\nOpen the two PNGs and read the "UAV ENU ... U=" line to confirm.')
    node.destroy_node()
    rclpy.shutdown()
    return 0 if (ok_a and ok_b) else 1


if __name__ == '__main__':
    sys.exit(main())
