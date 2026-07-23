#include "precision_landing/box_link.hpp"

namespace precision_landing
{

BoxLink::BoxLink(rclcpp::Node * node, int box_id, int drone_id)
: node_(node), box_id_(box_id), drone_id_(drone_id)
{
  // Matches box_state_manager.cpp: create_service("b" + box_id + "/cmd")
  const std::string cmd_topic = "b" + std::to_string(box_id_) + "/cmd";
  cli_cmd_ = node_->create_client<dib_msgs::srv::BoxCmd>(cmd_topic);

  RCLCPP_INFO(
    node_->get_logger(),
    "BoxLink: box_id=%d drone_id=%d, cmd service '%s', agent_id=%lu",
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
  request_accepted_ = false;
  last_request_time_ = 0.0;
  power_off_sent_ = false;
  power_off_confirmed_ = false;
  last_power_off_time_ = 0.0;
}

void BoxLink::request_landing()
{
  if (request_accepted_) {
    return;  // already acknowledged, nothing more to do
  }

  const double now = now_sec();
  if (request_sent_ && (now - last_request_time_) < REQUEST_RETRY_SEC) {
    return;  // request in flight, give the box time to answer
  }

  if (!cli_cmd_->service_is_ready()) {
    // Non-blocking probe. Do NOT wait_for_service() here - this runs inside
    // the control loop and blocking would stall the OFFBOARD setpoint stream.
    RCLCPP_WARN_THROTTLE(
      node_->get_logger(), *node_->get_clock(), 2000,
      "BoxLink: b%d/cmd service not available yet", box_id_);
    return;
  }

  auto req = std::make_shared<dib_msgs::srv::BoxCmd::Request>();
  req->command = dib_msgs::msg::BoxCmd::REQUEST_LANDING;
  // agent_id % 10 == 2 selects the drone branch; agent_id / 10 tells the box
  // which drone is asking (box_state_manager.cpp sets drone_id_ from this).
  req->agent_id = static_cast<uint64_t>(drone_id_) * 10 + AGENT_ROLE_DRONE;
  req->reserve = 0;

  request_sent_ = true;
  last_request_time_ = now;

  RCLCPP_INFO(
    node_->get_logger(), "BoxLink: sending REQUEST_LANDING to b%d (agent_id=%lu)",
    box_id_, static_cast<unsigned long>(req->agent_id));

  cli_cmd_->async_send_request(
    req,
    [this](rclcpp::Client<dib_msgs::srv::BoxCmd>::SharedFuture future) {
      const bool ok = future.get()->success;
      if (ok) {
        request_accepted_ = true;
        RCLCPP_INFO(node_->get_logger(), "BoxLink: REQUEST_LANDING accepted by box");
      } else {
        // box_state_manager only accepts REQUEST_LANDING while box_state ==
        // EMPTY. A rejection usually means the box is still busy from a
        // previous cycle; allow the retry timer to try again.
        request_sent_ = false;
        RCLCPP_WARN(
          node_->get_logger(),
          "BoxLink: REQUEST_LANDING rejected (box_state=%u, expected EMPTY=0). Retrying.",
          box_state_);
      }
    });
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

  if (!cli_cmd_->service_is_ready()) {
    RCLCPP_WARN_THROTTLE(
      node_->get_logger(), *node_->get_clock(), 2000,
      "BoxLink: b%d/cmd service not available for TURN_OFF_DRONE", box_id_);
    return;
  }

  auto req = std::make_shared<dib_msgs::srv::BoxCmd::Request>();
  req->command = dib_msgs::msg::BoxCmd::TURN_OFF_DRONE;
  req->agent_id = static_cast<uint64_t>(drone_id_) * 10 + AGENT_ROLE_DRONE;
  req->reserve = 0;

  power_off_sent_ = true;
  last_power_off_time_ = now;

  RCLCPP_INFO(
    node_->get_logger(), "BoxLink: sending TURN_OFF_DRONE to b%d (agent_id=%lu)",
    box_id_, static_cast<unsigned long>(req->agent_id));

  // The reply is ignored on purpose: it is hard-coded to success=true before
  // the box evaluates anything. Confirmation comes from box_state == CHARGING.
  cli_cmd_->async_send_request(
    req,
    [this](rclcpp::Client<dib_msgs::srv::BoxCmd>::SharedFuture future) {
      (void)future.get();
    });
}

}  // namespace precision_landing
