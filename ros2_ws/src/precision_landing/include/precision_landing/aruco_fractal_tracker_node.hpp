/*
 * This file is part of the aruco_fractal_tracker distribution (https://github.com/dimianx/aruco_fractal_tracker).
 * Copyright (c) 2024-2025 Dmitry Anikin <dmitry.anikin@proton.me>.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef PRECISION_LANDING__ARUCO_FRACTAL_TRACKER_NODE_HPP_
#define PRECISION_LANDING__ARUCO_FRACTAL_TRACKER_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/float32.hpp>
#include <dib_msgs/msg/landing_target6_d.hpp>
#include <dib_msgs/msg/box_telemetry.hpp>
#include <tf2/LinearMath/Matrix3x3.h>
#include <tf2/LinearMath/Vector3.h>
#include <tf2_ros/transform_broadcaster.h>

#include <aruco/fractaldetector.h>
#include <chrono>
#include <deque>
#include <utility>
#include <memory>
#include <opencv2/opencv.hpp>

namespace fractal_tracker
{
class ArucoFractalTracker : public rclcpp::Node
{
public:
  explicit ArucoFractalTracker(const rclcpp::NodeOptions& options);

private:
  aruco::FractalDetector detector_;

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr camera_info_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr uav_pose_sub_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr lander_state_sub_;
  rclcpp::Subscription<dib_msgs::msg::BoxTelemetry>::SharedPtr box_telemetry_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr glare_comp_sub_;

  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_pub_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr marker_pose_pub_;
  rclcpp::Publisher<dib_msgs::msg::LandingTarget6D>::SharedPtr target_pub_;

  /**
   * Overlay pose/image clock skew, in milliseconds; -1 when the two clocks are
   * not comparable at all (MAVROS not on the simulation clock).
   *
   * A topic rather than a log line on purpose. The tracker terminal already
   * carries several messages per second, so an extra periodic INFO is lost in
   * the scroll -- and the HUD field it mirrors was being clipped by the panel
   * width. This can be read on its own:
   *     ros2 topic echo /landing/pose_sync_ms
   */
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr pose_sync_pub_;
  std::shared_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;

  geometry_msgs::msg::PoseStamped::SharedPtr last_uav_pose_;
  // Short history of UAV poses so the debug overlay can be drawn with the pose
  // that was true AT THE IMAGE'S TIMESTAMP, not the newest pose available. The
  // image arrives queued behind the gz bridge, so using the newest pose paints
  // an altitude that disagrees with the marker distance measured from that same
  // frame (observed: 0.75 m apart during a 0.4 m/s descent in 7b).
  std::deque<std::pair<double, geometry_msgs::msg::PoseStamped::SharedPtr>> uav_pose_history_;
  static constexpr double kPoseHistorySec = 5.0;
  double last_overlay_pose_skew_s_{0.0};   // image stamp - chosen pose stamp
  /// UAV pose time-matched to the frame currently being processed. Set at the
  /// top of imageCallback and used by both the overlay and acceptPose()'s
  /// altitude sanity gate, so the two never disagree about when "now" is.
  geometry_msgs::msg::PoseStamped::SharedPtr frame_pose_;
  /// Newest pose no later than `stamp`, else the closest available.
  geometry_msgs::msg::PoseStamped::SharedPtr poseAt(double stamp);

  sensor_msgs::msg::CameraInfo last_camera_info_;
  bool camera_info_initialized_{false};

  double marker_size_;
  double min_tracking_z_{0.15};
  double max_tracking_z_{12.0};
  double max_pose_jump_m_{2.0};
  double camera_x_to_east_sign_{-1.0};
  double camera_y_to_north_sign_{1.0};
  double camera_offset_x_{0.1517};
  double camera_offset_y_{0.0};
  int acquire_good_frames_{5};
  int lost_bad_frames_{3};
  int good_frame_count_{0};
  int bad_frame_count_{0};
  uint8_t tracking_state_{dib_msgs::msg::LandingTarget6D::LOST};
  bool have_last_tvec_{false};
  tf2::Vector3 last_tvec_{0.0, 0.0, 0.0};
  bool show_latency_overlay_{true};
  double latency_warn_ms_{100.0};
  size_t frame_count_{0};
  size_t detection_count_{0};
  double last_processing_latency_ms_{0.0};
  double last_source_latency_ms_{0.0};
  bool source_latency_valid_{false};

  /**
   * Rolling floor of (now - image_stamp), used to separate REAL transport
   * latency from a CLOCK OFFSET between the camera and this node.
   *
   * `now() - header.stamp` only measures latency when both ends share a clock.
   * When they do not -- a camera that stamps from its own epoch, an embedded
   * companion whose NTP has drifted -- the same subtraction yields the offset,
   * and it looks exactly like a huge, alarming latency. That is what made the
   * HITL runs report enormous tracker e2e latency on the embedded computer
   * while `processing` (measured with steady_clock, offset-immune) stayed at a
   * few milliseconds.
   *
   * The two are told apart by their shape, not their size:
   *   real latency  -- small floor, visible jitter frame to frame
   *   clock offset  -- large floor, almost no jitter
   *
   * So track the minimum over a window. JITTER = raw - floor is offset-free and
   * is the number worth watching; a large, steady floor is the offset itself.
   */
  std::deque<std::pair<double, double>> latency_floor_win_;   // (t_sec, raw_ms)
  double latency_floor_ms_{0.0};
  double latency_jitter_ms_{0.0};
  bool latency_floor_valid_{false};
  static constexpr double kLatencyFloorWinSec = 10.0;
  /// A floor above this is reported as a suspected clock offset, not latency.
  static constexpr double kClockOffsetSuspectMs = 250.0;
  rclcpp::Time last_no_detection_log_;
  /**
   * Last tracking_state_ that was written to the log, so the detection line
   * reports a TRANSITION (LOST -> SEARCHING -> TRACKING) instead of repeating
   * once a second for the whole flight. 255 = nothing logged yet, so the very
   * first frame always announces the state it started in.
   */
  uint8_t last_logged_tracking_state_{255};

  /// Human-readable name for a LandingTarget6D tracking state.
  static const char * trackingStateName(uint8_t s)
  {
    switch (s) {
      case dib_msgs::msg::LandingTarget6D::LOST:      return "LOST";
      case dib_msgs::msg::LandingTarget6D::SEARCHING: return "SEARCHING";
      case dib_msgs::msg::LandingTarget6D::TRACKING:  return "TRACKING";
      default:                                        return "INIT";
    }
  }

  rclcpp::Time last_pose_log_;
  rclcpp::Time last_pose_failed_log_;
  rclcpp::Time last_latency_log_;
  std::string last_detected_ids_str_{"None"};
  std::string last_lander_state_{"UNKNOWN"};
  double last_box_yaw_{0.0};
  bool last_box_yaw_valid_{false};
  uint8_t last_box_state_{0};
  bool last_box_state_valid_{false};
  rclcpp::Time last_box_telemetry_time_;
  double current_fps_{0.0};
  rclcpp::Time last_fps_time_;
  rclcpp::Time last_valid_pose_time_;
  size_t fps_frame_count_{0};

  long last_sys_total_{0};
  long last_sys_idle_{0};
  long last_proc_ticks_{0};
  double system_cpu_usage_{0.0};
  double process_cpu_usage_{0.0};
  double last_marker_distance_{0.0};
  bool last_marker_distance_valid_{false};

  // Glare compensation parameters & state
  bool enable_glare_compensation_{false};
  bool enable_shadow_compensation_{false};
  double glare_gamma_{0.4};
  int clahe_clip_limit_{3};
  int clahe_tile_size_{8};
  bool glare_active_{false};
  cv::Ptr<cv::CLAHE> clahe_;

  bool getSystemCPUStats(long &idle, long &total) const;
  bool getProcessCPUStats(long &proc_ticks) const;
  void drawTransparentRect(cv::Mat& image, const cv::Rect& rect, const cv::Scalar& color, double alpha) const;
  cv::Mat preprocessForGlare(const cv::Mat& gray);

  void imageCallback(const sensor_msgs::msg::Image::SharedPtr msg);
  void cameraInfoCallback(const sensor_msgs::msg::CameraInfo::SharedPtr msg);
  void drawLatencyOverlay(cv::Mat& image);
  // Human-readable name for a dib_msgs::msg::BoxState value, for the HUD.
  static const char* boxStateName(uint8_t state);
  bool acceptPose(const tf2::Vector3& tvec, std::string& reject_reason);
  void publishTarget(
    const std_msgs::msg::Header& header,
    const tf2::Vector3& tvec,
    const tf2::Matrix3x3& rotation,
    int32_t tag_id);
  void publishTrackerStateOnly(const std_msgs::msg::Header& header);
}; // class ArucoFractalTracker
}  // namespace fractal_tracker

#endif  // PRECISION_LANDING__ARUCO_FRACTAL_TRACKER_NODE_HPP_
