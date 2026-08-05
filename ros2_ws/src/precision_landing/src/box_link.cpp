#include "precision_landing/box_link.hpp"

namespace precision_landing
{

BoxLink::BoxLink(rclcpp::Node * node, int box_id, int drone_id)
: node_(node), box_id_(box_id), drone_id_(drone_id)
{
  // Matches box_state_manager.cpp: create_subscription("b" + box_id + "/drone_cmd")
  const std::string cmd_topic = "b" + std::to_string(box_id_) + "/drone_cmd";
  pub_cmd_ = node_->create_publisher<dib_msgs::msg::BoxCmd>(cmd_topic, 10);

  RCLCPP_INFO(
    node_->get_logger(),
    "BoxLink: box_id=%d drone_id=%d, cmd topic '%s', agent_id=%lu",
    box_id_, drone_id_, cmd_topic.c_str(),
    static_cast<unsigned long>(drone_id_ * 10 + AGENT_ROLE_DRONE));
}

double BoxLink::now_sec() const
{
  return node_->get_clock()->now().seconds();
}

void BoxLink::set_box_state(uint8_t state)
{
  if (!has_box_state_ || state != box_state_) {
    RCLCPP_INFO(
      node_->get_logger(), "BoxLink: box_state %u -> %u",
      has_box_state_ ? box_state_ : 255u, state);
  }
  box_state_ = state;
  has_box_state_ = true;

  // Latch on first sight - see is_ready() for why this must not be a live test.
  if (state == dib_msgs::msg::BoxState::WAITING_FOR_LANDING && !box_ready_latched_) {
    box_ready_latched_ = true;
    RCLCPP_INFO(node_->get_logger(), "BoxLink: box reported WAITING_FOR_LANDING - ready latched");
  }

  // M3.6. CHARGING is the observable end of the securing sequence, and the
  // only trustworthy sign that TURN_OFF_DRONE was acted on.
  if (state == dib_msgs::msg::BoxState::CHARGING && !power_off_confirmed_) {
    power_off_confirmed_ = true;
    RCLCPP_INFO(node_->get_logger(), "BoxLink: box reached CHARGING - drone secured and powered off");
  }
}

bool BoxLink::is_ready() const
{
  return box_ready_latched_;
}

void BoxLink::reset()
{
  box_ready_latched_ = false;
  request_sent_ = false;
  last_request_time_ = 0.0;
  power_off_sent_ = false;
  power_off_confirmed_ = false;
  last_power_off_time_ = 0.0;
}

void BoxLink::request_landing()
{
  if (is_ready()) {
    return;  // box already confirmed WAITING_FOR_LANDING via telemetry
  }

  const double now = now_sec();
  if (request_sent_ && (now - last_request_time_) < REQUEST_RETRY_SEC) {
    return;  // published recently, give the box time to act and telemetry to catch up
  }

  auto msg = dib_msgs::msg::BoxCmd();
  msg.command = dib_msgs::msg::BoxCmd::REQUEST_LANDING;
  // agent_id % 10 == 2 selects the drone branch; agent_id / 10 tells the box
  // which drone is asking (box_state_manager.cpp sets drone_id_ from this).
  msg.agent_id = static_cast<uint64_t>(drone_id_) * 10 + AGENT_ROLE_DRONE;
  msg.reserve = 0;

  request_sent_ = true;
  last_request_time_ = now;

  RCLCPP_INFO(
    node_->get_logger(), "BoxLink: publishing REQUEST_LANDING to b%d (agent_id=%lu)",
    box_id_, static_cast<unsigned long>(msg.agent_id));

  pub_cmd_->publish(msg);
}

void BoxLink::request_power_off()
{
  if (power_off_confirmed_) {
    return;  // box already moved on to CHARGING
  }

  // box_state_manager.cpp only inspects TURN_OFF_DRONE while the box is in
  // SECURING_DRONE. Outside that window the command is dropped in silence, so
  // do not waste retries on it.
  if (box_state_ != dib_msgs::msg::BoxState::SECURING_DRONE) {
    return;
  }

  const double now = now_sec();
  if (power_off_sent_ && (now - last_power_off_time_) < REQUEST_RETRY_SEC) {
    return;
  }

  auto msg = dib_msgs::msg::BoxCmd();
  msg.command = dib_msgs::msg::BoxCmd::TURN_OFF_DRONE;
  msg.agent_id = static_cast<uint64_t>(drone_id_) * 10 + AGENT_ROLE_DRONE;
  msg.reserve = 0;

  power_off_sent_ = true;
  last_power_off_time_ = now;

  RCLCPP_INFO(
    node_->get_logger(), "BoxLink: publishing TURN_OFF_DRONE to b%d (agent_id=%lu)",
    box_id_, static_cast<unsigned long>(msg.agent_id));

  // Confirmation comes from box_state == CHARGING, not a reply -- see
  // power_off_confirmed()'s doc.
  pub_cmd_->publish(msg);
}

}  // namespace precision_landing
