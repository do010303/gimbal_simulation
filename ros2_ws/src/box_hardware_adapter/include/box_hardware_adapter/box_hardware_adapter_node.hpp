#ifndef BOX_HARDWARE_ADAPTER_NODE_HPP
#define BOX_HARDWARE_ADAPTER_NODE_HPP

#include <optional>
#include <string>

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/joint_state.hpp>
#include <trajectory_msgs/msg/joint_trajectory.hpp>

#include <dib_msgs/msg/lid_status.hpp>
#include <dib_msgs/msg/clamp_status.hpp>
#include <dib_msgs/msg/charge_status.hpp>
#include <dib_msgs/msg/cooling_status.hpp>
#include <dib_msgs/srv/lid_cmd.hpp>
#include <dib_msgs/srv/clamp_cmd.hpp>
#include <dib_msgs/srv/power_button_cmd.hpp>
#include <std_msgs/msg/bool.hpp>
#include <dib_msgs/srv/charge_cmd.hpp>
#include <dib_msgs/srv/cooling_cmd.hpp>

// BoxHardwareAdapterNode
// ----------------------
// Sits between box_manager (which speaks the dib_msgs service/topic contract)
// and box_simulation (which only exposes raw ros2_control JointTrajectory
// topics + /joint_states). It is the SITL replacement for the real box's
// embedded hardware layer.
//
//   box_manager  ──dib_msgs srv/msg──▶  THIS NODE  ──JointTrajectory──▶  box_simulation (Gazebo)
//                ◀──status topics────              ◀───/joint_states───
//
// See README.md for the unit mapping (rad/metre -> LidStatus/ClampStatus)
// and the explicitly-stubbed charge/cooling/power behaviour.
class BoxHardwareAdapterNode : public rclcpp::Node
{
public:
  BoxHardwareAdapterNode();

private:
  // --- /joint_states feedback -> status topics ---
  void jointStateCallback(const sensor_msgs::msg::JointState::SharedPtr msg);
  static std::optional<double> findJoint(
    const sensor_msgs::msg::JointState & msg, const std::string & name);
  void publishLidStatus(double lid_pos_rad);
  void publishClampStatus(double clamp_h_m, double clamp_v_m);

  // --- Service servers (adapter is the server; box_manager is the client) ---
  void lidCmdCallback(
    const dib_msgs::srv::LidCmd::Request::SharedPtr req,
    dib_msgs::srv::LidCmd::Response::SharedPtr res);
  void clampCmdCallback(
    const dib_msgs::srv::ClampCmd::Request::SharedPtr req,
    dib_msgs::srv::ClampCmd::Response::SharedPtr res);
  void powerButtonCmdCallback(
    const dib_msgs::srv::PowerButtonCmd::Request::SharedPtr req,
    dib_msgs::srv::PowerButtonCmd::Response::SharedPtr res);
  void chargeCmdCallback(
    const dib_msgs::srv::ChargeCmd::Request::SharedPtr req,
    dib_msgs::srv::ChargeCmd::Response::SharedPtr res);
  void coolingCmdCallback(
    const dib_msgs::srv::CoolingCmd::Request::SharedPtr req,
    dib_msgs::srv::CoolingCmd::Response::SharedPtr res);

  // --- Trajectory goal helpers ---
  void sendTrajectory(
    const rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr & pub,
    const std::string & joint_name, double target);

  // --- Parameters (with box_simulation-derived defaults) ---
  double lid_open_rad_{1.57};       // box.xacro lid_left_joint upper limit
  double lid_closed_rad_{0.0};      // box.xacro lid_left_joint lower limit
  double lid_settle_eps_rad_{0.05}; // ~3 deg band counted as "settled"
  double clamp_open_m_{0.0};        // box.xacro clamp_*_1_joint lower limit
  double clamp_closed_m_{0.2};      // box.xacro clamp_*_1_joint upper limit (full close)
  double mm_per_metre_{1000.0};     // ClampStatus reported in mm: round(m * 1000)
  double traj_time_from_start_s_{2.0};
  double status_stub_period_s_{0.2};

  // Feedback subscription
  rclcpp::Subscription<sensor_msgs::msg::JointState>::SharedPtr joint_state_sub_;

  // Command publishers -> box_simulation's JointTrajectoryControllers
  rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr lid_traj_pub_;
  rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr clamp_h_traj_pub_;
  rclcpp::Publisher<trajectory_msgs::msg::JointTrajectory>::SharedPtr clamp_v_traj_pub_;

  // Status publishers (box_manager subscribes to these)
  rclcpp::Publisher<dib_msgs::msg::LidStatus>::SharedPtr lid_status_pub_;
  rclcpp::Publisher<dib_msgs::msg::ClampStatus>::SharedPtr clamp_status_pub_;
  rclcpp::Publisher<dib_msgs::msg::ChargeStatus>::SharedPtr charge_status_pub_;
  rclcpp::Publisher<dib_msgs::msg::CoolingStatus>::SharedPtr cooling_status_pub_;
  rclcpp::TimerBase::SharedPtr stub_status_timer_;

  // Services served
  rclcpp::Service<dib_msgs::srv::LidCmd>::SharedPtr lid_cmd_srv_;
  rclcpp::Service<dib_msgs::srv::ClampCmd>::SharedPtr clamp_cmd_srv_;
  rclcpp::Service<dib_msgs::srv::PowerButtonCmd>::SharedPtr power_button_cmd_srv_;

  /// M3.6 SITL fixture: dock power rail state (true = drone powered).
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr drone_power_pub_;
  rclcpp::Service<dib_msgs::srv::ChargeCmd>::SharedPtr charge_cmd_srv_;
  rclcpp::Service<dib_msgs::srv::CoolingCmd>::SharedPtr cooling_cmd_srv_;

  // Delta-comparison state for lid OPENING/CLOSING inference
  // (mirrors box_manager::clamp_status_callback's own idiom).
  dib_msgs::msg::LidStatus last_lid_status_;
  bool have_prev_lid_sample_{false};
  double prev_lid_pos_rad_{0.0};

  // Stubbed charge/cooling state (no physics model — see README).
  dib_msgs::msg::ChargeStatus charge_status_;
  dib_msgs::msg::CoolingStatus cooling_status_;
};

#endif  // BOX_HARDWARE_ADAPTER_NODE_HPP
