#ifndef PRECISION_LANDING__MAVROS_TO_DIB_TELEMETRY_NODE_HPP_
#define PRECISION_LANDING__MAVROS_TO_DIB_TELEMETRY_NODE_HPP_

#include <string>

#include <rclcpp/rclcpp.hpp>
#include <mavros_msgs/msg/state.hpp>
#include <mavros_msgs/msg/extended_state.hpp>
#include <dib_msgs/msg/drone_telemetry.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>

namespace precision_landing
{

// MavrosToDibTelemetryNode
// ------------------------
// Bridges MAVROS state topics to the dib_msgs telemetry contract that
// box_manager subscribes to. Drone-side (companion computer) counterpart of
// box_hardware_adapter.
//
//   /mavros/state          ┐
//   /mavros/extended_state ┴─▶  THIS NODE  ─▶  d<drone_id>/telemetry (dib_msgs/DroneTelemetry)
//
// Replaces the M1 shortcut of hand-publishing a one-shot DroneTelemetry:
// box_manager can now transition WAITING_FOR_LANDING -> SECURING_DRONE off a
// real PX4 land-detector signal.
//
// TODO(M2+): battery bridging (/mavros/battery -> dib_msgs/BatteryStatus) is
// intentionally out of scope — box_manager's FSM consumes only landed_state.
class MavrosToDibTelemetryNode : public rclcpp::Node
{
public:
  explicit MavrosToDibTelemetryNode(
    const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  void onMavrosState(const mavros_msgs::msg::State::SharedPtr msg);
  void onExtendedState(const mavros_msgs::msg::ExtendedState::SharedPtr msg);
  void onLanderState(const std_msgs::msg::String::SharedPtr msg);
  void publishTelemetry();

  int drone_id_{1};
  std::string telemetry_topic_;

  rclcpp::Subscription<mavros_msgs::msg::State>::SharedPtr state_sub_;
  rclcpp::Subscription<mavros_msgs::msg::ExtendedState>::SharedPtr ext_state_sub_;
  rclcpp::Publisher<dib_msgs::msg::DroneTelemetry>::SharedPtr telemetry_pub_;

  dib_msgs::msg::DroneTelemetry telemetry_msg_;
  bool have_state_{false};
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr drone_power_sub_;

  bool have_ext_state_{false};

  /// M3.6: dock power rail. False = box cut power, so stop publishing.
  bool powered_{true};

  /// REQ_UAV_FLY_0020: mirrors the controller's /lander/state. True while the
  /// lander FSM is in FALLBACK, so DroneTelemetry.error carries code 0002.
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr lander_state_sub_;
  bool fallback_active_{false};
};

}  // namespace precision_landing

#endif  // PRECISION_LANDING__MAVROS_TO_DIB_TELEMETRY_NODE_HPP_
