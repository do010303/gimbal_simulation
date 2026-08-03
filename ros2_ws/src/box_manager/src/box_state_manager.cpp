#include "box_state_manager.hpp"
#include "dib_msgs/msg/box_cmd.hpp"
#include "dib_msgs/msg/state.hpp"
#include "dib_msgs/msg/battery_status.hpp"
#include <thread>


#define X_ANTEN_GPS_OFFSET 0.2
#define Y_ANTEN_GPS_OFFSET -1.9
#define Z_ANTEN_GPS_OFFSET -1.5
#define YAW_BOX 0.0

#define LANDING_TIMEOUT 120

#define CLAMP_H_CLOSE_TIMEOUT 30

void transformLocal2Global(double x_offset, double y_offset , double z_offset, double yaw, double &xG, double &yG, double &zG){
    double xL_rot = x_offset * cos(yaw) - y_offset * sin(yaw);
    double yL_rot = x_offset * sin(yaw) + y_offset * cos(yaw);
    xG = xL_rot + xG;
    yG = yL_rot + yG;
    zG = z_offset + zG;
  }


BoxStateManager::BoxStateManager() : Node("box_state_manager")
{
    this->box_state_ = BoxState::EMPTY;
    this->drone_id_ = 0;

    rclcpp::QoS qos(rclcpp::QoSInitialization(
      rmw_qos_history_policy_t::RMW_QOS_POLICY_HISTORY_KEEP_LAST,
      1  // Queue depth
    ));
    qos.reliability(rmw_qos_reliability_policy_t::RMW_QOS_POLICY_RELIABILITY_RELIABLE);
    qos.durability(rmw_qos_durability_policy_t::RMW_QOS_POLICY_DURABILITY_VOLATILE);

    this->declare_parameter("box_id",1);
    this->declare_parameter("pos_clamp_h_close",500);
    this->declare_parameter("pos_clamp_v_close",500);

    this->declare_parameter("x_anten_gps_offset", X_ANTEN_GPS_OFFSET);
    this->declare_parameter("y_anten_gps_offset", Y_ANTEN_GPS_OFFSET);
    this->declare_parameter("z_anten_gps_offset", Z_ANTEN_GPS_OFFSET);
    this->declare_parameter("yaw_box", YAW_BOX);

    this->box_id_ = this->get_parameter("box_id").as_int();
    this->pos_clamp_h_close = this->get_parameter("pos_clamp_h_close").as_int();
    this->pos_clamp_v_close = this->get_parameter("pos_clamp_v_close").as_int();
    x_anten_gps_offset = this->get_parameter("x_anten_gps_offset").as_double();
    y_anten_gps_offset = this->get_parameter("y_anten_gps_offset").as_double();
    z_anten_gps_offset = this->get_parameter("z_anten_gps_offset").as_double();
    yaw_box = this->get_parameter("yaw_box").as_double();

    // Create subscribers
    // box_pose_sub_ = this->create_subscription<dib_msgs::msg::BoxPose>("box/pose", 10, std::bind(&BoxStateManager::box_pose_callback, this, std::placeholders::_1));
    wind_sub_ = this->create_subscription<dib_msgs::msg::WindSensor>("env/outside/wind", 10, std::bind(&BoxStateManager::wind_callback, this, std::placeholders::_1));
    temp_inside_sub_ = this->create_subscription<dib_msgs::msg::Temperature>("system1/temperature2", 10, std::bind(&BoxStateManager::temp_inside_callback, this, std::placeholders::_1));
    temp_outside_sub_ = this->create_subscription<dib_msgs::msg::Temperature>("env/outside/temperature", 10, std::bind(&BoxStateManager::temp_outside_callback, this, std::placeholders::_1));
    humidity_inside_sub_ = this->create_subscription<dib_msgs::msg::Humidity>("system1/humidity1", 10, std::bind(&BoxStateManager::humidity_inside_callback, this, std::placeholders::_1));
    humidity_outside_sub_ = this->create_subscription<dib_msgs::msg::Humidity>("env/outside/humidity", 10, std::bind(&BoxStateManager::humidity_outside_callback, this, std::placeholders::_1));
    rain_sub_ = this->create_subscription<dib_msgs::msg::Rain>("env/outside/rain", 10, std::bind(&BoxStateManager::rain_callback, this, std::placeholders::_1));
    lid_status_sub_ = this->create_subscription<dib_msgs::msg::LidStatus>("/lid/status", 10, std::bind(&BoxStateManager::lid_status_callback, this, std::placeholders::_1));
    clamp_status_sub_ = this->create_subscription<dib_msgs::msg::ClampStatus>("/clamp/status", 10, std::bind(&BoxStateManager::clamp_status_callback, this, std::placeholders::_1));
    charge_status_sub_ = this->create_subscription<dib_msgs::msg::ChargeStatus>("/dock/charge/status", 10, std::bind(&BoxStateManager::charge_status_callback, this, std::placeholders::_1));
    cooling_status_sub_ = this->create_subscription<dib_msgs::msg::CoolingStatus>("/dock/cooling_battery/status", 10, std::bind(&BoxStateManager::cooling_status_callback, this, std::placeholders::_1));
    battery_temp_sub_ = this->create_subscription<dib_msgs::msg::Temperature>("/dock/battery/temperature", 10, std::bind(&BoxStateManager::battery_temp_callback, this, std::placeholders::_1));
    anten_gps_sub = this->create_subscription<sensor_msgs::msg::NavSatFix>("gps", 10, std::bind(&BoxStateManager::gps_callback, this, std::placeholders::_1));
    rtk_info_sub_ = this->create_subscription<dib_msgs::msg::RTKInfo>("rtk_info", 10, std::bind(&BoxStateManager::rtk_info_callback, this, std::placeholders::_1));
    power_status_sub_ = this->create_subscription<dib_msgs::msg::PowerStatus>("/system1/power/status", 10, std::bind(&BoxStateManager::power_status_callback, this, std::placeholders::_1));
    drone_id_sub_ = this->create_subscription<std_msgs::msg::UInt64>("/drone_id", 10, std::bind(&BoxStateManager::drone_id_callback, this, std::placeholders::_1));
    // Create publishers
    box_telemetry_pub_ = this->create_publisher<dib_msgs::msg::BoxTelemetry>("b" + std::to_string(this->box_id_) + "/telemetry", qos);
    box_state_pub_ = this->create_publisher<dib_msgs::msg::BoxState>("/box/state", 1);
    // Create subscribers for box telemetry (trick for ROS2)
    // box_telemetry_sub_ = this->create_subscription<dib_msgs::msg::BoxTelemetry>("b" + std::to_string(this->box_id_) + "/telemetry", 10, std::bind(&BoxStateManager::box_telemetry_callback, this, std::placeholders::_1));
    // Create Services
    box_cmd_service_ = this->create_service<dib_msgs::srv::BoxCmd>("b" + std::to_string(this->box_id_) + "/cmd", std::bind(&BoxStateManager::box_cmd_callback, this, std::placeholders::_1, std::placeholders::_2));
    mission_upload_service_ = this->create_service<dib_msgs::srv::MissionUpload>("box/mission_upload", std::bind(&BoxStateManager::mission_upload_callback, this, std::placeholders::_1, std::placeholders::_2));
    
    // Create clients for the services
    lid_cmd_client_ = this->create_client<dib_msgs::srv::LidCmd>("/lid/cmd");
    power_button_cmd_client_ = this->create_client<dib_msgs::srv::PowerButtonCmd>("/dock/power_button/cmd");
    charge_cmd_client_ = this->create_client<dib_msgs::srv::ChargeCmd>("/dock/charge/cmd");
    cooling_cmd_client_ = this->create_client<dib_msgs::srv::CoolingCmd>("/dock/cooling_battery/cmd");
    clamp_cmd_client_ = this->create_client<dib_msgs::srv::ClampCmd>("/clamp/cmd");
    
    
    // Create a timer
    box_telemetry_timer_ = this->create_wall_timer(200ms, std::bind(&BoxStateManager::box_telemetry_timer_callback, this));
    box_state_timer_ = this->create_wall_timer(100ms, std::bind(&BoxStateManager::state_machine_timer_callback, this));

    this->preparing_state_manager_ = new PreparingStateManager(this);
    this->securing_state_manager_ = new SecuringStateManager(this);
}

BoxStateManager::~BoxStateManager()
{
    delete this->preparing_state_manager_;
    delete this->securing_state_manager_;
}

void BoxStateManager::box_telemetry_callback(const dib_msgs::msg::BoxTelemetry::SharedPtr msg)
{
    this->box_telemetry_msg_trick_ = *msg;
}

void BoxStateManager::drone_id_callback(const std_msgs::msg::UInt64::SharedPtr msg)
{
    this->drone_id_ = msg->data;
    RCLCPP_INFO(this->get_logger(), "Drone ID received: %lu", this->drone_id_);
}

void BoxStateManager::wind_callback(const dib_msgs::msg::WindSensor::SharedPtr msg)
{
    box_environment_msg_.wind_speed = msg->wind_speed;
    box_environment_msg_.wind_direction = msg->wind_direction;
}

void BoxStateManager::temp_inside_callback(const dib_msgs::msg::Temperature::SharedPtr msg)
{
    box_environment_msg_.inside_temp = msg->temperature;
}

void BoxStateManager::temp_outside_callback(const dib_msgs::msg::Temperature::SharedPtr msg)
{
    box_environment_msg_.outside_temp = msg->temperature;
}

void BoxStateManager::humidity_inside_callback(const dib_msgs::msg::Humidity::SharedPtr msg)
{
    box_environment_msg_.inside_hum = msg->humidity;
}

void BoxStateManager::humidity_outside_callback(const dib_msgs::msg::Humidity::SharedPtr msg)
{
    box_environment_msg_.outside_hum = msg->humidity;
}

void BoxStateManager::rain_callback(const dib_msgs::msg::Rain::SharedPtr msg){
    box_environment_msg_.rain = msg->rain;
}

void BoxStateManager::drone_telemetry_callback(const dib_msgs::msg::DroneTelemetry::SharedPtr msg)
{
    if (!this->have_drone_telemetry_ || msg->state.connected != this->last_drone_connected_) {
        RCLCPP_INFO(this->get_logger(), "Drone telemetry connected=%d", msg->state.connected);
        this->last_drone_connected_ = msg->state.connected;
        this->have_drone_telemetry_ = true;
    }
    drone_telemetry_msg_ = *msg;

    // this->box_state_ = checkNewState((BoxState)msg->box_state);
    // runStateMachine(this->box_state_);
}

void BoxStateManager::lid_status_callback(const dib_msgs::msg::LidStatus::SharedPtr msg)
{
    lid_status_msg_ = *msg;
    if(msg->lid_status == msg->CLOSED) box_info_msg_.lid_state = box_info_msg_.CLOSED;
    else if(msg->lid_status == msg->OPENED) box_info_msg_.lid_state = box_info_msg_.OPENED;
    else if(msg->lid_status == msg->CLOSING) box_info_msg_.lid_state = box_info_msg_.CLOSING;
    else if(msg->lid_status == msg->OPENING) box_info_msg_.lid_state = box_info_msg_.OPENING;
    
}

void BoxStateManager::clamp_status_callback(const dib_msgs::msg::ClampStatus::SharedPtr msg)
{
    if(abs(msg->clamp_h_pos - this->pos_clamp_h_close) < 10 && abs(msg->clamp_v_pos - this->pos_clamp_v_close) < 10)  box_info_msg_.clamp_state = box_info_msg_.CLOSED;
    else if (msg->clamp_h_pos <= 10 && msg->clamp_v_pos <= 10)  box_info_msg_.clamp_state = box_info_msg_.OPENED;
    if(msg->clamp_h_pos - this->clamp_status_msg_.clamp_h_pos > 0) box_info_msg_.clamp_state = box_info_msg_.CLOSING;
    else if(msg->clamp_h_pos - this->clamp_status_msg_.clamp_h_pos < 0) box_info_msg_.clamp_state = box_info_msg_.OPENING;
    clamp_status_msg_ = *msg;
}

void BoxStateManager::charge_status_callback(const dib_msgs::msg::ChargeStatus::SharedPtr msg)
{
    charge_status_msg_ = *msg;
}

void BoxStateManager::cooling_status_callback(const dib_msgs::msg::CoolingStatus::SharedPtr msg)
{
    this->box_info_msg_.cooling_battery_state = msg->cooling_status;
}

void BoxStateManager::battery_temp_callback(const dib_msgs::msg::Temperature::SharedPtr msg)
{
    this->battery_temp_msg_ = *msg;
}

void BoxStateManager::gps_callback(const sensor_msgs::msg::NavSatFix::SharedPtr msg)
{
    double xG, yG, zG;
    std::string zone;
    NavsatConversions::LLtoUTM( msg->latitude, msg->longitude, yG, xG, zone);
    zG = msg->altitude;
    transformLocal2Global(x_anten_gps_offset, y_anten_gps_offset, z_anten_gps_offset, yaw_box, xG, yG, zG);
    NavsatConversions::UTMtoLL(yG, xG, zone, this->box_info_msg_.latitude, this->box_info_msg_.longitude);
    this->box_info_msg_.yaw = yaw_box;
}

void BoxStateManager::rtk_info_callback(const dib_msgs::msg::RTKInfo::SharedPtr msg)
{
    box_telemetry_msg_.rtk_info = *msg;
}

void BoxStateManager::power_status_callback(const dib_msgs::msg::PowerStatus::SharedPtr msg)
{
    this->box_power_msg_.voltage_power = msg->battery_voltage;
}

void BoxStateManager::box_cmd_callback(const std::shared_ptr<dib_msgs::srv::BoxCmd::Request> request, std::shared_ptr<dib_msgs::srv::BoxCmd::Response> response)
{
    response->success = true;
    std::thread([this, request, response]()
    {
        RCLCPP_INFO(this->get_logger(), "Box command received: %d", request->command);   
        if(request->agent_id % 10 == 0)
        {
            uint32_t start_time = rclcpp::Clock().now().seconds();
            switch (request->command)
            {
            case dib_msgs::msg::BoxCmd::OPEN_BOX:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: OPEN_BOX");
                this->lid_cmd(1);
                break;
            case dib_msgs::msg::BoxCmd::CLOSE_BOX:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: CLOSE_BOX");
                this->lid_cmd(0);
                break;
            case dib_msgs::msg::BoxCmd::TURN_ON_DRONE:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: TURN_ON_DRONE");
                this->power_button_cmd(1);
                break;
            case dib_msgs::msg::BoxCmd::TURN_OFF_DRONE:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: TURN_OFF_DRONE");
                this->power_button_cmd(0);
                break;
            case dib_msgs::msg::BoxCmd::START_CHARGING:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: START_CHARGING");
                this->start_charge = true;
                break;
            case dib_msgs::msg::BoxCmd::STOP_CHARGING:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: STOP_CHARGING");
                this->stop_charge = true;
                break;
            case dib_msgs::msg::BoxCmd::COOLING_ON:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: COOLING_ON");
                this->cooling_cmd(1);
                break;
            case dib_msgs::msg::BoxCmd::COOLING_OFF:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: COOLING_OFF");
                this->cooling_cmd(0);
                break;
            case dib_msgs::msg::BoxCmd::HOLD_DRONE:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: HOLD_DRONE");
                this->clamp_cmd(0, this->pos_clamp_h_close, this->pos_clamp_v_close, 1);
                while (this->clamp_status_msg_.clamp_h_pos != this->pos_clamp_h_close && rclcpp::Clock().now().seconds() - start_time < CLAMP_H_CLOSE_TIMEOUT)
                {
                    // RCLCPP_INFO(this->get_logger(), "Waiting for clamp h to hold the drone");
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));
                }
                this->clamp_cmd(0, this->pos_clamp_h_close, this->pos_clamp_v_close, 2);
                break;
            case dib_msgs::msg::BoxCmd::RELEASE_DRONE:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: RELEASE_DRONE");
                this->clamp_cmd(0, 0, 0, 3);
                break;
            case dib_msgs::msg::BoxCmd::PAIR_DRONE:
                /*code*/
                RCLCPP_DEBUG(this->get_logger(), "Box command: PAIR_DRONE");
                this->add_drone = true;
                this->drone_id_ = request->reserve;   
                break;
            case dib_msgs::msg::BoxCmd::UNPAIR_DRONE:
                /*code*/
                RCLCPP_DEBUG(this->get_logger(), "Box command: UNPAIR_DRONE");
                if (this->box_state_ == BoxState::IDLE)
                {
                    this->remove_drone = true;
                    this->drone_id_ = 0;
                }
                break;
            case dib_msgs::msg::BoxCmd::CLEAR_ERROR:
                /* code */
                RCLCPP_DEBUG(this->get_logger(), "Box command: CLEAR_ERROR");
                if (this->box_state_ == BoxState::ERROR)
                {
                    this->clear_error = true;
                }
                break;
            default:
                break;
            }
        }
        else if(request->agent_id % 10 == 2)
        {
            if(this->box_state_ == BoxState::EMPTY && request->command == dib_msgs::msg::BoxCmd::REQUEST_LANDING)
            {
                this->add_drone = true;
                this->drone_id_ = request->agent_id / 10;
                this->request_landing = true;
            }
            if(this->box_state_ == BoxState::SECURING_DRONE && request->command == dib_msgs::msg::BoxCmd::TURN_OFF_DRONE)
            {
                this->request_poweroff = true;
            }
        }
    }).detach();
}

void BoxStateManager::mission_upload_callback(const std::shared_ptr<dib_msgs::srv::MissionUpload::Request> request, std::shared_ptr<dib_msgs::srv::MissionUpload::Response> response)
{
    // RCLCPP_INFO(this->get_logger(), "Mission upload received");
    if(request->id % 10 == 1)
    {
        if(this->box_state_ == BoxState::IDLE)
        {   
            response->success = true;
            mission_received = true;
            this->mission_ = request->mission; 
            RCLCPP_INFO(this->get_logger(), "Mission upload received %ld, %ld",this->mission_.size(), request->mission.size());
        } else response->success = false;
    }
    else response->success = false;
    // Implement the logic for mission upload
}

void BoxStateManager::box_telemetry_timer_callback()
{
    this->box_telemetry_msg_.header.stamp = this->now();
    this->box_telemetry_msg_.header.frame_id = "b" + std::to_string(this->box_id_);
    this->box_info_msg_.drone_id = this->drone_id_;
    this->box_info_msg_.box_id = this->box_id_;
    this->box_info_msg_.yaw = this->yaw_box;
    // REQ_BOX_FEA_0003: spec-named fields (additive) derived from existing state.
    this->box_info_msg_.status_door = this->box_info_msg_.lid_state;
    this->box_info_msg_.status_hold = this->box_info_msg_.clamp_state;
    this->box_info_msg_.is_empty =
        (this->box_state_msg_.state == dib_msgs::msg::BoxState::EMPTY);
    this->box_info_msg_.connected = this->drone_telemetry_msg_.state.connected;
    this->box_info_msg_.air_conditioner =
        (this->box_info_msg_.cooling_battery_state != 0) ?
        dib_msgs::msg::BoxInfo::AC_ON : dib_msgs::msg::BoxInfo::AC_OFF;
    this->box_power_msg_.status_power = dib_msgs::msg::BoxPower::POWER_MAIN;
    this->box_telemetry_msg_.box_info = this->box_info_msg_;
    this->box_telemetry_msg_.box_environment = this->box_environment_msg_;
    this->box_telemetry_msg_.box_state = this->box_state_msg_;
    this->box_telemetry_msg_.box_power = this->box_power_msg_;
    this->box_telemetry_msg_.drone_battery_status.status_charge = this->charge_status_msg_.charge_status;
    this->box_telemetry_msg_.drone_battery_status.voltage = this->charge_status_msg_.v_bat;
    this->box_telemetry_msg_.drone_battery_status.voltage_charge = this->charge_status_msg_.v_bat; 
    this->box_telemetry_msg_.drone_battery_status.current_charge = this->charge_status_msg_.i_bat;
    this->box_telemetry_msg_.drone_battery_status.temperature = this->battery_temp_msg_.temperature;
    this->box_telemetry_msg_.drone_battery_status.time_charge = this->time_charge;

    this->box_telemetry_pub_->publish(this->box_telemetry_msg_);
    this->box_state_pub_->publish(this->box_state_msg_);
}

void BoxStateManager::state_machine_timer_callback()
{
    // Check the current state and run the state machine
    BoxState new_box_state = checkNewState(this->box_state_);
    runStateMachine(new_box_state);
}



void BoxStateManager::runStateMachine(BoxState new_state)
{
    if (this->box_state_ != new_state)
    {
        RCLCPP_INFO(this->get_logger(), "BoxStateManager state changed from %d to %d", (int)this->box_state_, (int)new_state);
        this->box_state_msg_.state = (uint8_t)new_state;
        this->box_state_ = new_state;
        this->change_state = true;
        this->change_state_time = rclcpp::Clock().now().seconds();
        // Sub-FSMs restart from NONE on every entry; clear the log memory with
        // them so the next cycle reports its first sub-state transition.
        this->last_logged_preparing_state_ = PreparingState::NONE;
        this->last_logged_securing_state_  = SecuringState::NONE;
    }
    else
    {
        this->change_state = false;
    }
    switch (new_state)
    {
        case BoxState::EMPTY:
            emptyState();
            break;
        case BoxState::IDLE:
            idleState();
            break;
        case BoxState::PREPARING_FOR_TAKEOFF:
            preparingForTakeoffState();
            break;
        case BoxState::MISSION_UPLOADING:
            missionUploadingState();
            break;
        case BoxState::WAITING_FOR_TAKEOFF:
            waitingForTakeoffState();
            break;
        case BoxState::WAITING_FOR_RETURN:
            waitingForReturnState();
            break;
        case BoxState::PREPARING_FOR_LANDING:
            preparingForLandingState();
            break;
        case BoxState::WAITING_FOR_LANDING:
            waitingForLandingState();
            break;
        case BoxState::SECURING_DRONE:
            securingDroneState();
            break;
        case BoxState::CHARGING:
            chargingState();
            break;
        case BoxState::MAINTAINING:
            maintainingState();
            break;
        case BoxState::ERROR:
            errorState();
            break;
        default:
            RCLCPP_ERROR(this->get_logger(), "Unknown state");
            break;
    }
}

BoxState BoxStateManager::checkNewState(BoxState state)
{
    BoxState new_state = state;
    switch (state)
    {
    case BoxState::EMPTY:
        /* code */
        if (this->add_drone) {
            new_state = BoxState::IDLE;
            this->add_drone = false;
        }
        break;
    case BoxState::IDLE:
        /* code */
        if (this->mission_received) {
            new_state = BoxState::PREPARING_FOR_TAKEOFF;
            this->mission_received = false;
        }
        if (this->request_landing) {
            new_state = BoxState::PREPARING_FOR_LANDING;
            this->request_landing = false;
        }
        if (this->remove_drone) {
            new_state = BoxState::EMPTY;
            this->remove_drone = false;
        }
        if (this->start_charge){
            new_state = BoxState::CHARGING;
            this->start_charge = false;
        }
        break;
    case BoxState::PREPARING_FOR_TAKEOFF:

        if (this->preparing_state_manager_->state == PreparingState::DONE) {
            new_state = BoxState::MISSION_UPLOADING;
            // this->preparing_state_manager_->state = PreparingState::NONE;
        }else if (this->preparing_state_manager_->state == PreparingState::FAILED) {
            new_state = BoxState::ERROR;
            this->box_state_error_ = BoxStateError::PREPARING_FOR_TAKEOFF_FAILED;
            this->box_info_msg_.error.push_back((int)this->box_state_error_ + (int)this->preparing_state_manager_->error*100);
            // this->preparing_state_manager_->state = PreparingState::NONE;
        }
        /* code */
        break;
    case BoxState::MISSION_UPLOADING:
        /* code */
        if (this->mission_upload_state == 1) {
            new_state = BoxState::WAITING_FOR_TAKEOFF;
        }
        if (this->mission_upload_state == 2)
        {
            new_state = BoxState::ERROR;
            this->box_state_error_ = BoxStateError::MISSION_UPLOADING_FAILED;
            this->box_info_msg_.error.push_back((int)this->box_state_error_);
        }
        break;
    case BoxState::WAITING_FOR_TAKEOFF:
        /* code */
        if (this->drone_telemetry_msg_.state.landed_state == dib_msgs::msg::State::LANDED_STATE_IN_AIR) {
            new_state = BoxState::EMPTY;
        }
        if (rclcpp::Clock().now().seconds() - this->change_state_time > 90) {
            new_state = BoxState::ERROR;
            this->box_state_error_ = BoxStateError::WAITING_FOR_TAKEOFF_FAILED;
            this->box_info_msg_.error.push_back((int)this->box_state_error_);
        }
        break;
    case BoxState::WAITING_FOR_RETURN:
        /* code */
        if (this->request_landing) {
            new_state = BoxState::PREPARING_FOR_LANDING;
            this->request_landing = false;
        }
        break;
    case BoxState::PREPARING_FOR_LANDING:
        /* code */
        if (this->preparing_state_manager_->state == PreparingState::DONE) {
            new_state = BoxState::WAITING_FOR_LANDING;
        }
        else if (this->preparing_state_manager_->state == PreparingState::FAILED) {
            new_state = BoxState::ERROR;
            this->box_state_error_ = BoxStateError::PREPARING_FOR_LANDING_FAILED;
            this->box_info_msg_.error.push_back((int)this->box_state_error_ + (int)this->preparing_state_manager_->error*100);
        }
        break;
    case BoxState::WAITING_FOR_LANDING:
        /* code */
        if (this->drone_telemetry_msg_.state.landed_state == dib_msgs::msg::State::LANDED_STATE_ON_GROUND) {
            new_state = BoxState::SECURING_DRONE;
        }
        if(rclcpp::Clock().now().seconds() - this->change_state_time > LANDING_TIMEOUT) {
            new_state = BoxState::ERROR;
            this->box_state_error_ = BoxStateError::WAITING_FOR_LANDING_FAILED;
            this->box_info_msg_.error.push_back((int)this->box_state_error_);
        }
        break;
    case BoxState::SECURING_DRONE:
        /* code */
        if (this->securing_state_manager_->state == SecuringState::DONE) {
            new_state = BoxState::CHARGING;
            // securing_state_ = SecuringState::NONE;
        }
        else if (this->securing_state_manager_->state == SecuringState::FAILED) {
            new_state = BoxState::ERROR;;
            this->box_state_error_ = BoxStateError::SECURING_DRONE_FAILED;
            this->box_info_msg_.error.push_back((int)this->box_state_error_);
            // securing_state_ = SecuringState::NONE;
        }
        break;
    case BoxState::CHARGING:
        /* code */
        if (this->charge_status_msg_.charge_status == dib_msgs::msg::ChargeStatus::CHARGE_DONE || (this->charge_status_msg_.fault_status == 16 && this->charge_status_msg_.charge_status == dib_msgs::msg::ChargeStatus::NOT_CHARGING)) {
            new_state = BoxState::IDLE;
            std::thread([this](){
                this->charge_cmd(0);
                this->cooling_cmd(0);
            }).detach();
        }
        if (this->stop_charge) {
            new_state = BoxState::IDLE;
            this->stop_charge = false;
            std::thread([this](){
                this->charge_cmd(0);
                this->cooling_cmd(0);
            }).detach();
        }
        break;
    case BoxState::MAINTAINING:
        /* code */
        break;
    case BoxState::ERROR:
        /* code */
        // if(this->box_state_error_ == BoxStateError::WAITING_FOR_LANDING_FAILED)
        // {
        //     new_state = BoxState::EMPTY;
        //     this->box_state_error_ = BoxStateError::NONE;
        //     this->box_info_msg_.error.clear();
        // }
        if(this->clear_error)
        {
            if(this->box_state_error_ == BoxStateError::WAITING_FOR_LANDING_FAILED) new_state = BoxState::EMPTY;
            else new_state = BoxState::IDLE;
            this->clear_error = false;
            this->box_state_error_ = BoxStateError::NONE;
            this->box_info_msg_.error.clear();
        }
        break;
    default:
        break;
    }
    return new_state;
}


void BoxStateManager::emptyState()
{
    // Implement the logic for the EMPTY state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in EMPTY state");
    }
    box_state_msg_.state = (uint8_t)BoxState::EMPTY;
    if(this->change_state) 
    {
        this->add_drone = false;
        std::thread([this]()
        {
            if(this->lid_status_msg_.lid_status == dib_msgs::msg::LidStatus::OPENED)
            {
                this->lid_cmd(0);
            }
        }).detach();
        this->drone_id_ = 0;
    }
    if (this->drone_telemetry_sub_) this->drone_telemetry_sub_.reset();
    if (this->mission_upload_client_) this->mission_upload_client_.reset();
}

void BoxStateManager::idleState()
{
    // Implement the logic for the IDLE state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in IDLE state");
    }
    box_state_msg_.state = (uint8_t)BoxState::IDLE;
    this->time_charge = 0;
    
    if(!this->drone_telemetry_sub_ && this->drone_id_ != 0) {
        rclcpp::QoS qos(rclcpp::QoSInitialization(
        rmw_qos_history_policy_t::RMW_QOS_POLICY_HISTORY_KEEP_LAST,
        1  // Queue depth
        ));
        qos.reliability(rmw_qos_reliability_policy_t::RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
        qos.durability(rmw_qos_durability_policy_t::RMW_QOS_POLICY_DURABILITY_VOLATILE);
        this->drone_telemetry_sub_ = this->create_subscription<dib_msgs::msg::DroneTelemetry>( "d" + std::to_string(this->drone_id_) + "/telemetry", qos, std::bind(&BoxStateManager::drone_telemetry_callback, this, std::placeholders::_1));
    }
    if(!this->mission_upload_client_ && this->drone_id_ != 0) {
        this->mission_upload_client_ = this->create_client<dib_msgs::srv::MissionUpload>("d" + std::to_string(this->drone_id_) + "/mission_upload");
    }
}

void BoxStateManager::preparingForTakeoffState()
{
    // Implement the logic for the PREPARING_FOR_TAKEOFF state
    box_state_msg_.state = (uint8_t)BoxState::PREPARING_FOR_TAKEOFF;

    if(this->change_state)
    {
        this->preparing_state_manager_->state = PreparingState::NONE;
        this->preparing_state_manager_->none(); // Reset the preparing state
    }
    PreparingState new_preparing_state = this->preparing_state_manager_->checkNewState(this->preparing_state_manager_->state);
    this->preparing_state_manager_->runStateMachine(new_preparing_state);
    if (this->preparing_state_manager_->state != this->last_logged_preparing_state_) {
        RCLCPP_INFO(this->get_logger(), "Box in PREPARING_FOR_TAKEOFF state, sub-state %d -> %d",
                    (int)this->last_logged_preparing_state_, (int)this->preparing_state_manager_->state);
        this->last_logged_preparing_state_ = this->preparing_state_manager_->state;
    }
}
void BoxStateManager::missionUploadingState()
{
    // Implement the logic for the MISSION_UNLOADING state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in MISSION_UPLOADING state");
    }
    box_state_msg_.state = (uint8_t)BoxState::MISSION_UPLOADING;
    this->mission_upload_state = 0;
    if(this->change_state)
    {
        std::thread([this]()
        {
            if(this->mission_upload_client_->wait_for_service(1s))
            {
                auto request = std::make_shared<dib_msgs::srv::MissionUpload::Request>();
                request->id = 1 + this->box_id_ * 10; 
                request->mission = this->mission_;
                RCLCPP_INFO(this->get_logger(), "NUmber of mission: %ld", request->mission.size());
                auto result = this->mission_upload_client_->async_send_request(request);
                this->mission_upload_state = 1; // Reset the state before sending the request
                // if (result.wait_for(3s) == std::future_status::ready) {
                //     auto response = result.get();
                //     if (response->success) {
                //         this->mission_upload_state = 1;
                //     } else {
                //         RCLCPP_ERROR(this->get_logger(), "Mission upload failed");
                //         this->mission_upload_state = 2;
                //     }
                // } else {
                //     RCLCPP_ERROR(this->get_logger(), "Failed to send mission upload");
                //     this->mission_upload_state = 2;
                // }
            }
            else
            {
                RCLCPP_ERROR(this->get_logger(), "Mission upload service not available");
                this->mission_upload_state = 2;
            }
        }).detach();
    }
}
void BoxStateManager::waitingForTakeoffState()
{
    // Implement the logic for the WAITING_FOR_TAKEOFF state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in WAITING_FOR_TAKEOFF state");
    }
    box_state_msg_.state = (uint8_t)BoxState::WAITING_FOR_TAKEOFF;
}
void BoxStateManager::waitingForReturnState()
{
    // Implement the logic for the WAITING_FOR_RETURN state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in WAITING_FOR_RETURN state");
    }
    box_state_msg_.state = (uint8_t)BoxState::WAITING_FOR_RETURN;
}
void BoxStateManager::preparingForLandingState()
{
    // Implement the logic for the PREPARING_FOR_LANDING state
    box_state_msg_.state = (uint8_t)BoxState::PREPARING_FOR_LANDING;
    if(this->change_state)
    {
        this->preparing_state_manager_->state = PreparingState::NONE;
        this->preparing_state_manager_->none(); // Reset the preparing state
    }
    PreparingState new_preparing_state = this->preparing_state_manager_->checkNewState(this->preparing_state_manager_->state);
    this->preparing_state_manager_->runStateMachine(new_preparing_state);
    if (this->preparing_state_manager_->state != this->last_logged_preparing_state_) {
        RCLCPP_INFO(this->get_logger(), "Box in PREPARING_FOR_LANDING state, sub-state %d -> %d",
                    (int)this->last_logged_preparing_state_, (int)this->preparing_state_manager_->state);
        this->last_logged_preparing_state_ = this->preparing_state_manager_->state;
    }
}
void BoxStateManager::waitingForLandingState()
{
    // Implement the logic for the WAITING_FOR_LANDING state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in WAITING_FOR_LANDING state");
    }
    box_state_msg_.state = (uint8_t)BoxState::WAITING_FOR_LANDING;
}
void BoxStateManager::securingDroneState()
{
    // Implement the logic for the SECURING_DRONE state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in SECURING_DRONE state");
    }
    box_state_msg_.state = (uint8_t)BoxState::SECURING_DRONE;
    if(this->change_state)
    {
        this->securing_state_manager_->state = SecuringState::NONE;
        this->securing_state_manager_->none(); // Reset the securing state
    }
    SecuringState new_securing_state = this->securing_state_manager_->checkNewState(this->securing_state_manager_->state);

    this->securing_state_manager_->runStateMachine(new_securing_state);
    if (this->securing_state_manager_->state != this->last_logged_securing_state_) {
        RCLCPP_INFO(this->get_logger(), "Box in SECURING_DRONE state, sub-state %d -> %d",
                    (int)this->last_logged_securing_state_, (int)this->securing_state_manager_->state);
        this->last_logged_securing_state_ = this->securing_state_manager_->state;
    }
}
void BoxStateManager::chargingState()
{
    // Implement the logic for the CHARGING state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in CHARGING state");
    }
    box_state_msg_.state = (uint8_t)BoxState::CHARGING;
    this->time_charge = rclcpp::Clock().now().seconds() - this->change_state_time;
    if(this->change_state)
    {
        // Detached thread, matching every other command call site in this
        // codebase (preparing_state_manager.cpp:179,208 and
        // securing_state_manager.cpp:27,47,66,85). charge_cmd() blocks on
        // result.wait_for(1s); called straight from the state-machine timer
        // callback that blocks the executor, so the reply can never be
        // processed and the call always "fails" after exactly 1.000 s -- even
        // though box_hardware_adapter had already answered it.
        std::thread([this]()
        {
            this->charge_cmd(1);
            this->cooling_cmd(1);
        }).detach();
    }

}
void BoxStateManager::maintainingState()
{
    // Implement the logic for the MAINTAINING state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in MAINTAINING state");
    }
    box_state_msg_.state = (uint8_t)BoxState::MAINTAINING;
}
void BoxStateManager::errorState()
{
    // Implement the logic for the ERROR state
    if (this->change_state || !this->logged_any_state_) {
        this->logged_any_state_ = true;
        RCLCPP_INFO(this->get_logger(), "Box in ERROR state");
    }
    box_state_msg_.state = (uint8_t)BoxState::ERROR;
}

uint8_t BoxStateManager::lid_cmd(int command)
{
    if (this->lid_cmd_client_->wait_for_service(1s)) {
        auto request = std::make_shared<dib_msgs::srv::LidCmd::Request>();
        request->command = command;
        auto result = this->lid_cmd_client_->async_send_request(request);
        if (result.wait_for(1s) == std::future_status::ready) {
            RCLCPP_INFO(this->get_logger(), "Lid command sent");
            return 1;
        } else {
            RCLCPP_ERROR(this->get_logger(), "Failed to send lid command");
        }
    } else {
        RCLCPP_ERROR(this->get_logger(), "Lid command service not available");
    }
    return 0;
}
uint8_t BoxStateManager::power_button_cmd(int command)
{
    if (this->power_button_cmd_client_->wait_for_service(1s)) {
        auto request = std::make_shared<dib_msgs::srv::PowerButtonCmd::Request>();
        request->command = command;
        auto result = this->power_button_cmd_client_->async_send_request(request);
        if (result.wait_for(1s) == std::future_status::ready) {
            RCLCPP_INFO(this->get_logger(), "Power button command sent");
            return 1;
        } else {
            RCLCPP_ERROR(this->get_logger(), "Failed to send power button command");
        }
    } else {
        RCLCPP_ERROR(this->get_logger(), "Power button command service not available");

    }
    return 0;
}
uint8_t BoxStateManager::cooling_cmd(int command)
{
    if (this->cooling_cmd_client_->wait_for_service(1s)) {
        auto request = std::make_shared<dib_msgs::srv::CoolingCmd::Request>();
        request->command = command;
        auto result = this->cooling_cmd_client_->async_send_request(request);
        if (result.wait_for(1s) == std::future_status::ready) {
            RCLCPP_INFO(this->get_logger(), "Cooling command sent");
            return 1;
        } else {
            RCLCPP_ERROR(this->get_logger(), "Failed to send cooling command");
        }
    } else {
        RCLCPP_ERROR(this->get_logger(), "Cooling command service not available");
    }
    return 0;
}
uint8_t BoxStateManager::charge_cmd(int command)
{
    if (this->charge_cmd_client_->wait_for_service(1s)) {
        auto request = std::make_shared<dib_msgs::srv::ChargeCmd::Request>();
        request->command = command;
        auto result = this->charge_cmd_client_->async_send_request(request);
        if (result.wait_for(1s) == std::future_status::ready) {
            RCLCPP_INFO(this->get_logger(), "Charge command sent");
            return 1;
        } else {
            RCLCPP_ERROR(this->get_logger(), "Failed to send charge command");
        }
    } else {
        RCLCPP_ERROR(this->get_logger(), "Charge command service not available");
    }
    return 0;
}
uint8_t BoxStateManager::clamp_cmd(int mode, int clamp_h_pos_cmd, int clamp_v_pos_cmd, int clamp_select)
{
    if (this->clamp_cmd_client_->wait_for_service(1s)) {
        auto request = std::make_shared<dib_msgs::srv::ClampCmd::Request>();
        request->mode = mode;
        request->clamp_h_pos_cmd = clamp_h_pos_cmd;
        request->clamp_v_pos_cmd = clamp_v_pos_cmd;
        request->clamp_select = clamp_select;
        auto result = this->clamp_cmd_client_->async_send_request(request);
        if (result.wait_for(1s) == std::future_status::ready) {
            RCLCPP_INFO(this->get_logger(), "Clamp command sent");
            return 1;
        } else {
            RCLCPP_ERROR(this->get_logger(), "Failed to send clamp command");
        }
    } else {
        RCLCPP_ERROR(this->get_logger(), "Clamp command service not available");
    }
    return 0;
}

int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<BoxStateManager>());
  rclcpp::shutdown();
  return 0;
}



