#include "box_hardware_adapter/box_hardware_adapter_node.hpp"

#include <cmath>
#include <functional>

using namespace std::chrono_literals;
using std::placeholders::_1;
using std::placeholders::_2;

BoxHardwareAdapterNode::BoxHardwareAdapterNode()
: Node("box_hardware_adapter")
{
  // --- Parameters (defaults come from box_simulation's box.xacro limits) ---
  lid_open_rad_          = declare_parameter("lid_open_rad", lid_open_rad_);
  lid_closed_rad_        = declare_parameter("lid_closed_rad", lid_closed_rad_);
  lid_settle_eps_rad_    = declare_parameter("lid_settle_eps_rad", lid_settle_eps_rad_);
  clamp_open_m_          = declare_parameter("clamp_open_m", clamp_open_m_);
  clamp_closed_m_        = declare_parameter("clamp_closed_m", clamp_closed_m_);
  mm_per_metre_          = declare_parameter("mm_per_metre", mm_per_metre_);
  traj_time_from_start_s_ = declare_parameter("traj_time_from_start_s", traj_time_from_start_s_);
  status_stub_period_s_  = declare_parameter("status_stub_period_s", status_stub_period_s_);

  // --- Feedback in: box_simulation's joint_state_broadcaster ---
  joint_state_sub_ = create_subscription<sensor_msgs::msg::JointState>(
    "/joint_states", 10,
    std::bind(&BoxHardwareAdapterNode::jointStateCallback, this, _1));

  // --- Command out: box_simulation's JointTrajectoryControllers ---
  lid_traj_pub_ = create_publisher<trajectory_msgs::msg::JointTrajectory>(
    "/joint_lid_controller/joint_trajectory", 10);
  clamp_h_traj_pub_ = create_publisher<trajectory_msgs::msg::JointTrajectory>(
    "/joint_clamp_h_controller/joint_trajectory", 10);
  clamp_v_traj_pub_ = create_publisher<trajectory_msgs::msg::JointTrajectory>(
    "/joint_clamp_v_controller/joint_trajectory", 10);

  // --- Status out: box_manager subscribes to these (unqualified topics,
  //     matching box_state_manager.cpp's own subscriptions) ---
  lid_status_pub_     = create_publisher<dib_msgs::msg::LidStatus>("/lid/status", 10);
  clamp_status_pub_   = create_publisher<dib_msgs::msg::ClampStatus>("/clamp/status", 10);
  charge_status_pub_  = create_publisher<dib_msgs::msg::ChargeStatus>("/dock/charge/status", 10);
  cooling_status_pub_ = create_publisher<dib_msgs::msg::CoolingStatus>("/dock/cooling_battery/status", 10);

  // M3.6 SITL fixture. Stands in for the dock power rail; see
  // powerButtonCmdCallback() for why it is needed. transient_local so a late
  // subscriber still learns the current state.
  drone_power_pub_ = create_publisher<std_msgs::msg::Bool>(
    "/dock/drone_power", rclcpp::QoS(1).transient_local());
  {
    std_msgs::msg::Bool initial;
    initial.data = true;   // the drone is powered until the box says otherwise
    drone_power_pub_->publish(initial);
  }

  // --- Services served (adapter is the server for box_manager's clients) ---
  lid_cmd_srv_ = create_service<dib_msgs::srv::LidCmd>(
    "/lid/cmd", std::bind(&BoxHardwareAdapterNode::lidCmdCallback, this, _1, _2));
  clamp_cmd_srv_ = create_service<dib_msgs::srv::ClampCmd>(
    "/clamp/cmd", std::bind(&BoxHardwareAdapterNode::clampCmdCallback, this, _1, _2));
  power_button_cmd_srv_ = create_service<dib_msgs::srv::PowerButtonCmd>(
    "/dock/power_button/cmd", std::bind(&BoxHardwareAdapterNode::powerButtonCmdCallback, this, _1, _2));
  charge_cmd_srv_ = create_service<dib_msgs::srv::ChargeCmd>(
    "/dock/charge/cmd", std::bind(&BoxHardwareAdapterNode::chargeCmdCallback, this, _1, _2));
  cooling_cmd_srv_ = create_service<dib_msgs::srv::CoolingCmd>(
    "/dock/cooling_battery/cmd", std::bind(&BoxHardwareAdapterNode::coolingCmdCallback, this, _1, _2));

  // Charge/cooling have no physical model in box_simulation: keep publishing
  // the last commanded stub value so box_manager always sees a fresh status.
  charge_status_.charge_status = dib_msgs::msg::ChargeStatus::NOT_CHARGING;
  cooling_status_.cooling_status = 0;
  stub_status_timer_ = create_wall_timer(
    std::chrono::duration<double>(status_stub_period_s_),
    [this]() {
      charge_status_pub_->publish(charge_status_);
      cooling_status_pub_->publish(cooling_status_);
    });

  RCLCPP_INFO(get_logger(),
    "box_hardware_adapter ready: serving /lid/cmd /clamp/cmd /dock/{power_button,charge,cooling_battery}/cmd, "
    "driving box_simulation JTCs, publishing /lid/status /clamp/status (mm)");
}

// ---------------------------------------------------------------------------
// /joint_states -> LidStatus / ClampStatus
// ---------------------------------------------------------------------------
std::optional<double> BoxHardwareAdapterNode::findJoint(
  const sensor_msgs::msg::JointState & msg, const std::string & name)
{
  // /joint_states ordering is not guaranteed -> always look up by name.
  for (size_t i = 0; i < msg.name.size(); ++i) {
    if (msg.name[i] == name && i < msg.position.size()) {
      return msg.position[i];
    }
  }
  return std::nullopt;
}

void BoxHardwareAdapterNode::jointStateCallback(
  const sensor_msgs::msg::JointState::SharedPtr msg)
{
  // Only the primary joints are read; mimic joints track them in sim.
  auto lid_pos = findJoint(*msg, "lid_left_joint");
  auto clamp_h = findJoint(*msg, "clamp_h_1_joint");
  auto clamp_v = findJoint(*msg, "clamp_v_1_joint");

  if (lid_pos) {
    publishLidStatus(*lid_pos);
  }
  if (clamp_h && clamp_v) {
    publishClampStatus(*clamp_h, *clamp_v);
  }
}

void BoxHardwareAdapterNode::publishLidStatus(double lid_pos_rad)
{
  dib_msgs::msg::LidStatus out;

  if (std::abs(lid_pos_rad - lid_closed_rad_) < lid_settle_eps_rad_) {
    out.lid_status = out.CLOSED;
  } else if (std::abs(lid_pos_rad - lid_open_rad_) < lid_settle_eps_rad_) {
    out.lid_status = out.OPENED;
  } else if (have_prev_lid_sample_ && lid_pos_rad > prev_lid_pos_rad_) {
    out.lid_status = out.OPENING;   // moving toward the open limit
  } else if (have_prev_lid_sample_ && lid_pos_rad < prev_lid_pos_rad_) {
    out.lid_status = out.CLOSING;   // moving toward the closed limit
  } else {
    out.lid_status = last_lid_status_.lid_status;  // no motion info yet: hold
  }

  prev_lid_pos_rad_ = lid_pos_rad;
  have_prev_lid_sample_ = true;
  last_lid_status_ = out;
  lid_status_pub_->publish(out);
}

void BoxHardwareAdapterNode::publishClampStatus(double clamp_h_m, double clamp_v_m)
{
  // ClampStatus carries raw positions only (no state enum). Report in mm so
  // box_manager's pos_clamp_h_close / pos_clamp_v_close params (set to 200 in
  // box_state_manager.yaml for the sim) match the sim's 0..0.2 m travel.
  // box_manager itself infers OPENED/CLOSED/OPENING/CLOSING downstream.
  dib_msgs::msg::ClampStatus out;
  out.clamp_h_pos = static_cast<int32_t>(std::lround(clamp_h_m * mm_per_metre_));
  out.clamp_v_pos = static_cast<int32_t>(std::lround(clamp_v_m * mm_per_metre_));
  clamp_status_pub_->publish(out);
}

// ---------------------------------------------------------------------------
// Trajectory goal helper
// ---------------------------------------------------------------------------
void BoxHardwareAdapterNode::sendTrajectory(
  const rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr & pub,
  const std::string & joint_name, double target)
{
  trajectory_msgs::msg::JointTrajectory traj;
  traj.joint_names = {joint_name};
  trajectory_msgs::msg::JointTrajectoryPoint pt;
  pt.positions = {target};
  pt.time_from_start = rclcpp::Duration::from_seconds(traj_time_from_start_s_);
  traj.points.push_back(pt);
  pub->publish(traj);
}

// ---------------------------------------------------------------------------
// Command services
// ---------------------------------------------------------------------------
void BoxHardwareAdapterNode::lidCmdCallback(
  const dib_msgs::srv::LidCmd::Request::SharedPtr req,
  dib_msgs::srv::LidCmd::Response::SharedPtr res)
{
  // dib_msgs contract: command 1 = open, 0 = close.
  const double target = (req->command == 1) ? lid_open_rad_ : lid_closed_rad_;
  RCLCPP_INFO(get_logger(), "/lid/cmd command=%d -> lid target %.3f rad", req->command, target);
  sendTrajectory(lid_traj_pub_, "lid_left_joint", target);
  // Fire-and-forget: real completion is observed by box_manager via /lid/status.
  res->success = true;
}

void BoxHardwareAdapterNode::clampCmdCallback(
  const dib_msgs::srv::ClampCmd::Request::SharedPtr req,
  dib_msgs::srv::ClampCmd::Response::SharedPtr res)
{
  // req->mode is always 0 at every box_manager call site -> accepted but ignored.
  // req->clamp_*_pos_cmd arrive in mm (adapter's own unit); convert to metres.
  const double h_m = req->clamp_h_pos_cmd / mm_per_metre_;
  const double v_m = req->clamp_v_pos_cmd / mm_per_metre_;

  // clamp_select: 1 = H only, 2 = V only, 3 = both.
  if (req->clamp_select == 1 || req->clamp_select == 3) {
    sendTrajectory(clamp_h_traj_pub_, "clamp_h_1_joint", h_m);
  }
  if (req->clamp_select == 2 || req->clamp_select == 3) {
    sendTrajectory(clamp_v_traj_pub_, "clamp_v_1_joint", v_m);
  }
  RCLCPP_INFO(get_logger(),
    "/clamp/cmd select=%d h_cmd=%d v_cmd=%d (mm) -> h=%.3f v=%.3f m",
    req->clamp_select, req->clamp_h_pos_cmd, req->clamp_v_pos_cmd, h_m, v_m);
  res->success = true;
}

void BoxHardwareAdapterNode::powerButtonCmdCallback(
  const dib_msgs::srv::PowerButtonCmd::Request::SharedPtr req,
  dib_msgs::srv::PowerButtonCmd::Response::SharedPtr res)
{
  // box_simulation has no dock power model, so the command itself is a stub.
  // What is NOT a stub is the consequence: on real hardware cutting dock power
  // kills the drone's companion computer, its telemetry stops, and that
  // silence is exactly what box_manager waits for --
  // SecuringStateManager::POWER_OFF leaves for DONE only when
  // drone_telemetry is older than 5 s (securing_state_manager.cpp:217-220),
  // and DONE is what moves the box on to CHARGING.
  //
  // Without modelling that, SITL deadlocks: MAVROS keeps running, telemetry
  // never goes stale, and the box sits in POWER_OFF forever -- the drone lands
  // and is clamped correctly but the cycle never completes.
  //
  // So publish the power state and let mavros_to_dib_telemetry (which stands
  // in for the companion computer) fall silent when it goes false. Latched, so
  // it works regardless of node start order.
  const bool powered = (req->command != 0);
  std_msgs::msg::Bool msg;
  msg.data = powered;
  drone_power_pub_->publish(msg);

  RCLCPP_INFO(
    get_logger(), "/dock/power_button/cmd command=%d -> drone power %s",
    req->command, powered ? "ON" : "OFF");
  res->success = true;
}

void BoxHardwareAdapterNode::chargeCmdCallback(
  const dib_msgs::srv::ChargeCmd::Request::SharedPtr req,
  dib_msgs::srv::ChargeCmd::Response::SharedPtr res)
{
  // Stubbed charge behaviour (no battery physics). Fixed placeholder v_bat/i_bat.
  charge_status_.charge_status = (req->command == 1)
    ? dib_msgs::msg::ChargeStatus::CHARGING
    : dib_msgs::msg::ChargeStatus::NOT_CHARGING;
  charge_status_.fault_status = 0;
  charge_status_.v_bat = 12.0f;
  charge_status_.i_bat = (req->command == 1) ? 2.0f : 0.0f;
  RCLCPP_INFO(get_logger(), "/dock/charge/cmd command=%d (stub)", req->command);
  res->success = true;
}

void BoxHardwareAdapterNode::coolingCmdCallback(
  const dib_msgs::srv::CoolingCmd::Request::SharedPtr req,
  dib_msgs::srv::CoolingCmd::Response::SharedPtr res)
{
  // Stubbed cooling behaviour (no thermal model).
  cooling_status_.cooling_status = (req->command == 1) ? 1 : 0;
  RCLCPP_INFO(get_logger(), "/dock/cooling_battery/cmd command=%d (stub)", req->command);
  res->success = true;
}
