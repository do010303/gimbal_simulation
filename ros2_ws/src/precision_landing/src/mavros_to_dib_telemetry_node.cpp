#include "precision_landing/mavros_to_dib_telemetry_node.hpp"

#include <functional>

#include <rclcpp_components/register_node_macro.hpp>

using std::placeholders::_1;

namespace precision_landing
{

MavrosToDibTelemetryNode::MavrosToDibTelemetryNode(const rclcpp::NodeOptions & options)
: Node("mavros_to_dib_telemetry_node", options)
{
  drone_id_ = declare_parameter("drone_id", drone_id_);
  telemetry_topic_ = "d" + std::to_string(drone_id_) + "/telemetry";

  // MAVROS publishes /mavros/state and /mavros/extended_state with a
  // TRANSIENT_LOCAL, RELIABLE, depth-1 profile — subscribe with a matching
  // sensor-data-friendly QoS so the latest sample is always available.
  rclcpp::QoS mavros_qos(rclcpp::QoSInitialization(RMW_QOS_POLICY_HISTORY_KEEP_LAST, 1));
  mavros_qos.reliability(RMW_QOS_POLICY_RELIABILITY_RELIABLE);
  mavros_qos.durability(RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL);

  state_sub_ = create_subscription<mavros_msgs::msg::State>(
    "/mavros/state", mavros_qos,
    std::bind(&MavrosToDibTelemetryNode::onMavrosState, this, _1));
  ext_state_sub_ = create_subscription<mavros_msgs::msg::ExtendedState>(
    "/mavros/extended_state", mavros_qos,
    std::bind(&MavrosToDibTelemetryNode::onExtendedState, this, _1));

  // box_manager's drone_telemetry_sub_ (see box_state_manager.cpp idleState())
  // uses BEST_EFFORT / VOLATILE / depth 1 — mirror it exactly on the publisher
  // side so the two ends match with no surprises.
  rclcpp::QoS telemetry_qos(rclcpp::QoSInitialization(RMW_QOS_POLICY_HISTORY_KEEP_LAST, 1));
  telemetry_qos.reliability(RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
  telemetry_qos.durability(RMW_QOS_POLICY_DURABILITY_VOLATILE);
  telemetry_pub_ = create_publisher<dib_msgs::msg::DroneTelemetry>(telemetry_topic_, telemetry_qos);

  RCLCPP_INFO(get_logger(),
    "mavros_to_dib_telemetry ready: /mavros/state + /mavros/extended_state -> %s",
    telemetry_topic_.c_str());
}

void MavrosToDibTelemetryNode::onMavrosState(const mavros_msgs::msg::State::SharedPtr msg)
{
  // Direct passthrough; armed/guided/manual_input/mode have no dib_msgs field.
  telemetry_msg_.state.connected = msg->connected;
  telemetry_msg_.state.system_status = msg->system_status;
  have_state_ = true;
  if (have_state_ && have_ext_state_) {
    publishTelemetry();
  }
}

void MavrosToDibTelemetryNode::onExtendedState(const mavros_msgs::msg::ExtendedState::SharedPtr msg)
{
  // LANDED_STATE_* constants are byte-identical between mavros_msgs and
  // dib_msgs (ON_GROUND=1, IN_AIR=2), so this is a straight passthrough.
  telemetry_msg_.state.landed_state = msg->landed_state;
  have_ext_state_ = true;
  if (have_state_ && have_ext_state_) {
    publishTelemetry();
  }
}

void MavrosToDibTelemetryNode::publishTelemetry()
{
  // Gated on having received at least one of each message so a zero-initialised
  // landed_state (LANDED_STATE_UNDEFINED=0) never reaches box_manager.
  telemetry_msg_.header.stamp = now();
  telemetry_msg_.header.frame_id = "d" + std::to_string(drone_id_);
  telemetry_pub_->publish(telemetry_msg_);
}

}  // namespace precision_landing

RCLCPP_COMPONENTS_REGISTER_NODE(precision_landing::MavrosToDibTelemetryNode)
