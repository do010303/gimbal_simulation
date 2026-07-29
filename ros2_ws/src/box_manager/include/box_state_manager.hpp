
#ifndef BOX_STATE_MANAGER_HPP
#define BOX_STATE_MANAGER_HPP

#include <chrono>
#include <functional>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "dib_msgs/msg/box_telemetry.hpp"
#include "dib_msgs/msg/box_environment.hpp"
#include "dib_msgs/msg/box_state.hpp"
#include "dib_msgs/msg/box_info.hpp"
#include "dib_msgs/msg/box_power.hpp"
#include "dib_msgs/msg/humidity.hpp"
#include "dib_msgs/msg/temperature.hpp"
#include "dib_msgs/msg/rain.hpp"
#include "dib_msgs/msg/wind_sensor.hpp"
#include "dib_msgs/msg/box_pose.hpp"
#include "dib_msgs/msg/drone_telemetry.hpp"
#include "dib_msgs/srv/box_cmd.hpp"
#include "dib_msgs/srv/lid_cmd.hpp"
#include "dib_msgs/srv/cooling_cmd.hpp"
#include "dib_msgs/srv/charge_cmd.hpp"
#include "dib_msgs/srv/power_button_cmd.hpp"
#include "dib_msgs/srv/clamp_cmd.hpp"
#include "dib_msgs/srv/mission_upload.hpp"
#include "dib_msgs/msg/mission_item.hpp"
#include "dib_msgs/msg/lid_status.hpp"
#include "dib_msgs/msg/charge_status.hpp"
#include "dib_msgs/msg/clamp_status.hpp"
#include "dib_msgs/msg/cooling_status.hpp"
#include "dib_msgs/msg/rtk_info.hpp"
#include "dib_msgs/msg/power_status.hpp"
#include "preparing_state_manager.hpp"
#include "securing_state_manager.hpp"
#include "sensor_msgs/msg/nav_sat_fix.hpp"
#include "navsat_conversion.h"
#include "std_msgs/msg/u_int64.hpp"

 

using namespace std::chrono_literals;


// class PreparingStateManager;
// class SecureStateManager;

enum class BoxState
{
    EMPTY = 0,
    IDLE = 1,
    PREPARING_FOR_TAKEOFF = 2,
    MISSION_UPLOADING = 3,
    WAITING_FOR_TAKEOFF = 4,
    WAITING_FOR_RETURN = 5,
    PREPARING_FOR_LANDING = 6,
    WAITING_FOR_LANDING = 7,
    SECURING_DRONE = 8,
    CHARGING = 9,
    MAINTAINING = 10,
    ERROR =  101
};

enum class BoxStateError
{
    NONE = 0,
    PREPARING_FOR_TAKEOFF_FAILED = 1,
    MISSION_UPLOADING_FAILED = 2,
    WAITING_FOR_TAKEOFF_FAILED = 3,
    WAITING_FOR_RETURN_FAILED = 4,
    PREPARING_FOR_LANDING_FAILED = 5,
    WAITING_FOR_LANDING_FAILED = 6,
    SECURING_DRONE_FAILED = 7,
    CHARGING_FAILED = 8,
};

class BoxStateManager : public rclcpp::Node
{
    public:
        friend class PreparingStateManager;
        friend class SecuringStateManager;
        BoxStateManager();
        ~BoxStateManager();

    private:
        // Callbacks
        // void gps_callback(const sensor_msgs::msg::NavSatFix::SharedPtr msg);
        void wind_callback(const dib_msgs::msg::WindSensor::SharedPtr msg);
        void temp_inside_callback(const dib_msgs::msg::Temperature::SharedPtr msg);
        void temp_outside_callback(const dib_msgs::msg::Temperature::SharedPtr msg);
        void humidity_inside_callback(const dib_msgs::msg::Humidity::SharedPtr msg);
        void humidity_outside_callback(const dib_msgs::msg::Humidity::SharedPtr msg);
        void rain_callback(const dib_msgs::msg::Rain::SharedPtr msg);
        void box_pose_callback(const dib_msgs::msg::BoxPose::SharedPtr msg);
        void drone_telemetry_callback(const dib_msgs::msg::DroneTelemetry::SharedPtr msg);
        void lid_status_callback(const dib_msgs::msg::LidStatus::SharedPtr msg);
        void clamp_status_callback(const dib_msgs::msg::ClampStatus::SharedPtr msg);
        void charge_status_callback(const dib_msgs::msg::ChargeStatus::SharedPtr msg);
        void gps_callback(const sensor_msgs::msg::NavSatFix::SharedPtr msg);
        void rtk_info_callback(const dib_msgs::msg::RTKInfo::SharedPtr msg);
        void power_status_callback(const dib_msgs::msg::PowerStatus::SharedPtr msg);
        void box_telemetry_callback(const dib_msgs::msg::BoxTelemetry::SharedPtr msg);
        void drone_id_callback(const std_msgs::msg::UInt64::SharedPtr msg);
        void cooling_status_callback(const dib_msgs::msg::CoolingStatus::SharedPtr msg);
        void battery_temp_callback(const dib_msgs::msg::Temperature::SharedPtr msg);

        
        // Service callbacks
        void box_cmd_callback(const std::shared_ptr<dib_msgs::srv::BoxCmd::Request> request, std::shared_ptr<dib_msgs::srv::BoxCmd::Response> response);
        void mission_upload_callback(const std::shared_ptr<dib_msgs::srv::MissionUpload::Request> request, std::shared_ptr<dib_msgs::srv::MissionUpload::Response> response);

        // Timer callbacks
        void box_telemetry_timer_callback();
        void state_machine_timer_callback();
        
        // State machine functions
        void emptyState();
        void idleState();
        void preparingForTakeoffState();
        void missionUploadingState();
        void waitingForTakeoffState();
        void waitingForReturnState();
        void preparingForLandingState();
        void waitingForLandingState();
        void securingDroneState();
        void chargingState();
        void maintainingState();
        void errorState();


        uint8_t lid_cmd(int command);
        uint8_t power_button_cmd(int command);
        uint8_t cooling_cmd(int command);
        uint8_t charge_cmd(int command);
        uint8_t clamp_cmd(int mode, int clamp_h_pos_cmd, int clamp_v_pos_cmd, int clamp_select);

        BoxState checkNewState(BoxState state); 
        void runStateMachine(BoxState new_state);
        void checkDroneOnline();

        // ROS2 Node
        rclcpp::Subscription<dib_msgs::msg::BoxPose>::SharedPtr box_pose_sub_;
        rclcpp::Subscription<dib_msgs::msg::Temperature>::SharedPtr temp_inside_sub_;
        rclcpp::Subscription<dib_msgs::msg::Temperature>::SharedPtr temp_outside_sub_;
        rclcpp::Subscription<dib_msgs::msg::Humidity>::SharedPtr humidity_inside_sub_;
        rclcpp::Subscription<dib_msgs::msg::Humidity>::SharedPtr humidity_outside_sub_;
        rclcpp::Subscription<dib_msgs::msg::Rain>::SharedPtr rain_sub_;
        rclcpp::Subscription<dib_msgs::msg::WindSensor>::SharedPtr wind_sub_;
        rclcpp::Subscription<dib_msgs::msg::LidStatus>::SharedPtr lid_status_sub_;
        rclcpp::Subscription<dib_msgs::msg::ClampStatus>::SharedPtr clamp_status_sub_;
        rclcpp::Subscription<dib_msgs::msg::ChargeStatus>::SharedPtr charge_status_sub_;
        rclcpp::Subscription<sensor_msgs::msg::NavSatFix>::SharedPtr anten_gps_sub;
        rclcpp::Subscription<dib_msgs::msg::DroneTelemetry>::SharedPtr drone_telemetry_sub_;
        rclcpp::Subscription<dib_msgs::msg::RTKInfo>::SharedPtr rtk_info_sub_;
        rclcpp::Subscription<dib_msgs::msg::PowerStatus>::SharedPtr power_status_sub_;
        rclcpp::Subscription<std_msgs::msg::UInt64>::SharedPtr drone_id_sub_;
        rclcpp::Subscription<dib_msgs::msg::CoolingStatus>::SharedPtr cooling_status_sub_;
        rclcpp::Subscription<dib_msgs::msg::Temperature>::SharedPtr battery_temp_sub_;


        rclcpp::Publisher<dib_msgs::msg::BoxTelemetry>::SharedPtr box_telemetry_pub_;
        rclcpp::Subscription<dib_msgs::msg::BoxTelemetry>::SharedPtr box_telemetry_sub_;
        rclcpp::Publisher<dib_msgs::msg::BoxState>::SharedPtr box_state_pub_;

        rclcpp::Service<dib_msgs::srv::BoxCmd>::SharedPtr box_cmd_service_;
        rclcpp::Service<dib_msgs::srv::MissionUpload>::SharedPtr mission_upload_service_;

        rclcpp::Client<dib_msgs::srv::LidCmd>::SharedPtr lid_cmd_client_;
        rclcpp::Client<dib_msgs::srv::CoolingCmd>::SharedPtr cooling_cmd_client_;
        rclcpp::Client<dib_msgs::srv::ChargeCmd>::SharedPtr charge_cmd_client_;
        rclcpp::Client<dib_msgs::srv::PowerButtonCmd>::SharedPtr power_button_cmd_client_;
        rclcpp::Client<dib_msgs::srv::ClampCmd>::SharedPtr clamp_cmd_client_;
        rclcpp::Client<dib_msgs::srv::MissionUpload>::SharedPtr mission_upload_client_;
        
        
        // rclcpp::TimerBase::SharedPtr state_machine_timer_; 
        rclcpp::TimerBase::SharedPtr box_telemetry_timer_;
        rclcpp::TimerBase::SharedPtr box_state_timer_;


        dib_msgs::msg::BoxTelemetry box_telemetry_msg_;
        dib_msgs::msg::BoxTelemetry box_telemetry_msg_trick_;
        dib_msgs::msg::BoxInfo box_info_msg_;
        dib_msgs::msg::BoxEnvironment box_environment_msg_;
        dib_msgs::msg::BoxState box_state_msg_;
        dib_msgs::msg::BoxPower box_power_msg_;
        dib_msgs::msg::DroneTelemetry drone_telemetry_msg_;
        dib_msgs::msg::LidStatus lid_status_msg_;
        dib_msgs::msg::ChargeStatus charge_status_msg_;
        dib_msgs::msg::ClampStatus clamp_status_msg_;
        dib_msgs::msg::CoolingStatus cooling_status_msg_;
        dib_msgs::msg::Temperature battery_temp_msg_;

        std::vector<dib_msgs::msg::MissionItem> mission_;
        uint64_t box_id_;
        uint64_t drone_id_;
        BoxState box_state_;

        BoxStateError box_state_error_;

        bool request_landing = false;   
        bool mission_received = false; 
        bool add_drone = false;
        bool remove_drone = false;
        bool drone_online = false;
        bool change_state = false;
        bool clear_error = false;

        bool start_charge = false;
        bool stop_charge = false;

        bool request_poweroff = false;

        uint16_t pos_clamp_h_close = 1000;
        uint16_t pos_clamp_v_close = 1000;
        uint8_t mission_upload_state; // 0 : not uploaded, 1 : uploaded 2: error

        double x_anten_gps_offset ;
        double y_anten_gps_offset ;
        double z_anten_gps_offset ;
        double yaw_box ;

        uint32_t change_state_time = 0;

        uint32_t time_charge = 0;

        PreparingStateManager* preparing_state_manager_;
        SecuringStateManager* securing_state_manager_;

        // Last logged sub-state, so the PREPARING_* and SECURING_DRONE lines
        // report a TRANSITION instead of repeating on every 100 ms tick. Same
        // idea as runStateMachine()'s box_state_ comparison, applied one level
        // down: the sub-FSMs advance on their own schedule, so change_state
        // alone would only ever show their first step.
        PreparingState last_logged_preparing_state_ = PreparingState::NONE;
        SecuringState  last_logged_securing_state_  = SecuringState::NONE;

        // box_state_ starts at EMPTY, so the first tick is not a transition
        // and change_state stays false. Without this the node would never
        // announce the state it booted into.
        bool logged_any_state_ = false;

        // Last logged drone link state; the telemetry callback fires per
        // message, so log the transition rather than the stream.
        bool last_drone_connected_ = false;
        bool have_drone_telemetry_ = false;

};

#endif