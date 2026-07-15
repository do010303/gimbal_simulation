#!/usr/bin/env python3
"""
ROS2 Auto-Exposure (AE) Analyzer — GUI version (crash-proof).

Subscribes to '/siyi/image_raw' from siyi_camera_bridge,
displays live feed with mean brightness overlay.

Fix for crash:
  1. Force X11 backend (avoid Wayland crash)
  2. Decouple image callback from GUI rendering
     — callback only stores latest frame (no accumulation)
     — separate timer renders GUI at fixed 15 Hz
"""
import os
# Force X11 backend BEFORE any GUI library loads
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['XDG_SESSION_TYPE'] = 'x11'
os.environ['GDK_BACKEND'] = 'x11'

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import time
import threading


class AeAnalyzerGui(Node):
    def __init__(self):
        super().__init__('ae_analyzer_gui')

        self.bridge = CvBridge()
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.history = []
        self.t0 = time.time()

        # Subscribe — only store latest frame, no heavy processing here
        self.create_subscription(Image, '/siyi/image_raw', self._on_image, 1)

        self.get_logger().info("AE Analyzer GUI started. Waiting for images on /siyi/image_raw ...")

    def _on_image(self, msg):
        """Lightweight callback: just convert and store latest frame."""
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            with self.frame_lock:
                self.latest_frame = frame
        except Exception as e:
            self.get_logger().error(f'cv_bridge: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = AeAnalyzerGui()

    # Spin ROS2 in a background thread so GUI runs on main thread
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    history = []
    t0 = time.time()

    try:
        while rclpy.ok():
            frame = None
            with node.frame_lock:
                if node.latest_frame is not None:
                    frame = node.latest_frame.copy()
                    node.latest_frame = None  # consume it

            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                mean_b = float(np.mean(gray))
                elapsed = time.time() - t0
                history.append((elapsed, mean_b))

                # HUD
                cv2.putText(frame, f"Mean Brightness: {mean_b:.1f}", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                cv2.putText(frame, f"Time: {elapsed:.1f}s", (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

                if len(history) > 30:
                    vals = [h[1] for h in history[-90:]]
                    spread = max(vals) - min(vals)
                    if spread > 25:
                        txt, clr = "AE ACTIVE (brightness adjusting)", (0, 255, 255)
                    else:
                        txt, clr = "AE stable or OFF", (0, 200, 0)
                    cv2.putText(frame, txt, (20, 120),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, clr, 2)

                cv2.imshow("SIYI A8 - AE Test", frame)

            key = cv2.waitKey(30) & 0xFF  # ~30 fps GUI refresh, non-blocking
            if key == ord('q'):
                break

    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.try_shutdown()

        # Print summary
        if len(history) > 10:
            vals = [h[1] for h in history]
            print(f"\n{'=' * 50}")
            print(f"  Frames: {len(history)}  Duration: {history[-1][0]:.1f}s")
            print(f"  Brightness — min: {min(vals):.1f}  max: {max(vals):.1f}  range: {max(vals) - min(vals):.1f}")
            print(f"{'=' * 50}")
            if max(vals) - min(vals) > 40:
                print("  → Camera HAS Auto-Exposure")
            else:
                print("  → AE may be OFF (or lighting was constant)")


if __name__ == '__main__':
    main()
