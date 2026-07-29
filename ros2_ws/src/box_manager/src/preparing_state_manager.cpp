#include "preparing_state_manager.hpp"
#include "box_state_manager.hpp"
#include <thread>
#include <ctime>
#define WAITING_TIMEOUT 90  // 90s
#define READY_TO_FLY_TIMEOUT 60 // 60s

PreparingStateManager::PreparingStateManager(BoxStateManager* box_state_manager)
{
    this->box_state_manager = box_state_manager;
    this->state = PreparingState::NONE;
    RCLCPP_INFO(this->box_state_manager->get_logger(), "PreparingStateManager initialized");
}

PreparingState PreparingStateManager::checkNewState(PreparingState state)
{
    // Implement the logic for checking new state
    PreparingState new_state = state;
    switch (state)
    {
        case PreparingState::NONE:
            if(this->box_state_manager->box_state_ == BoxState::PREPARING_FOR_TAKEOFF){
                new_state = PreparingState::CHECK_WEATHER_CONDITIONS;
            }
            if(this->box_state_manager->box_state_ == BoxState::PREPARING_FOR_LANDING){
                new_state = PreparingState::OPEN_BOX_AND_CLAMP;
            }
            break;
        case PreparingState::CHECK_WEATHER_CONDITIONS:
            if(this->weather_conditions_ok){
                new_state = PreparingState::POWER_ON_DRONE;
            }
            else{
                new_state = PreparingState::FAILED;
                this->error = PreparingStateError::WEATHER_CONDITIONS_FAIL;
            }
            break;
        case PreparingState::POWER_ON_DRONE:
            if (this->send_cmd_power_on == 1){
                new_state = PreparingState::WAITING_DRONE_READY;
            }else if (this->send_cmd_power_on == 2){
                new_state = PreparingState::FAILED;
                this->error = PreparingStateError::POWER_ON_FAIL;
            }
            break;
        case PreparingState::WAITING_DRONE_READY:
            if (this->drone_ready){
                new_state = PreparingState::OPEN_BOX_AND_CLAMP;
            }
            if(this->waiting_timeout){
                new_state = PreparingState::FAILED;
                this->error = PreparingStateError::WAITING_DRONE_READY_TIMEOUT;
            }
            break;
        case PreparingState::OPEN_BOX_AND_CLAMP:
            if(this->send_cmd_open_box_and_clamp == 1){
                new_state = PreparingState::WAITING_BOX_CLAMP_OPEN;
            }else if(this->send_cmd_open_box_and_clamp == 2){
                new_state = PreparingState::FAILED;
                this->error = PreparingStateError::CMD_OPEN_BOX_CLAMP_FAIL;
                
            }   
            break;
        case PreparingState::WAITING_BOX_CLAMP_OPEN:
            if (this->box_clamp_open){
                if(this->box_state_manager->box_state_ == BoxState::PREPARING_FOR_TAKEOFF){
                    new_state = PreparingState::WAITING_READY_TO_FLY;
                }
                if(this->box_state_manager->box_state_ == BoxState::PREPARING_FOR_LANDING){
                    new_state = PreparingState::DONE;
                }
                this->box_open = false;
            }
            if(this->waiting_timeout){
                new_state = PreparingState::FAILED;
                this->error = PreparingStateError::WAITING_BOX_CLAMP_OPEN_TIMEOUT;
            }
            break;
        case PreparingState::WAITING_READY_TO_FLY:
            if((rclcpp::Clock().now().seconds() - this->start_time) > READY_TO_FLY_TIMEOUT)
            {
                if(this->box_state_manager->drone_telemetry_msg_.state.system_status > 2){
                    new_state = PreparingState::DONE;
                }
                else{
                new_state = PreparingState::FAILED;
                this->error = PreparingStateError::WAITING_READY_TO_FLY_TIMEOUT;
                }
            }
            break;
        case PreparingState::DONE:
            // new_state = PreparingState::NONE;
            break;
        case PreparingState::FAILED:
            // new_state = PreparingState::NONE;
            break;
    }
    return new_state;
}

void PreparingStateManager::runStateMachine(PreparingState new_state)
{
    if(this->state != new_state)
    {
        this->change_state = true;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "PreparingStateManager state changed from %d to %d", (int)this->state, (int)new_state);
        this->start_time = rclcpp::Clock().now().seconds();
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Start time: %f", this->start_time);
        this->waiting_timeout = false;
        this->state = new_state;
    }else{
        this->change_state = false;
    }
    switch (new_state)
    {
        case PreparingState::NONE:;
            none();
            break;  
        case PreparingState::CHECK_WEATHER_CONDITIONS:
            checkWeatherConditions();
            break;
        case PreparingState::POWER_ON_DRONE:
            powerOnDrone();
            break;
        case PreparingState::WAITING_DRONE_READY:
            waitingDroneReady();
            break;
        case PreparingState::OPEN_BOX_AND_CLAMP:
            openBoxAndClamp();
            break;
        case PreparingState::WAITING_BOX_CLAMP_OPEN:
            waitingBoxClampOpen();
            break;
        case PreparingState::WAITING_READY_TO_FLY:
            waitingReadyToFly();
            break;
        case PreparingState::DONE:
            done();
            break;
        case PreparingState::FAILED:
            failed();
            break;
    }
}

void PreparingStateManager::none()
{
    this->drone_ready = false;
    this->box_clamp_open = false;
    this->send_cmd_open_box_and_clamp = 0;
    this->send_cmd_power_on = 0;
    this->waiting_timeout = false;
    this->weather_conditions_ok = false;
    this->error = PreparingStateError::NONE;
}

void PreparingStateManager::checkWeatherConditions()
{
    // Implement the logic for checking weather conditions
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Checking weather conditions");
    }
    state = PreparingState::CHECK_WEATHER_CONDITIONS;
    if (!this->box_state_manager->box_environment_msg_.rain && this->box_state_manager->box_environment_msg_.wind_speed < 7.0)
    {
        this->weather_conditions_ok = true;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Weather conditions ok");
    }
    else
    {
        this->weather_conditions_ok = false;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Weather conditions not ok");
    }
}
void PreparingStateManager::powerOnDrone()
{
    // Implement the logic for powering on the drone
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Powering on drone");
    }
    state = PreparingState::POWER_ON_DRONE;
    if (this->change_state){
        std::thread([this](){
            if (this->box_state_manager->power_button_cmd(1)) this->send_cmd_power_on = 1;
            else this->send_cmd_power_on = 2;
        }).detach();
    }
    
}
void PreparingStateManager::waitingDroneReady()
{
    // Implement the logic for waiting for the drone to be ready
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Waiting for drone to be ready");
    }
    state = PreparingState::WAITING_DRONE_READY;
    if(rclcpp::Clock().now().seconds() - this->box_state_manager->drone_telemetry_msg_.header.stamp.sec < 1)
    {
        this->drone_ready = true;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Drone ready");
    }
    else if((rclcpp::Clock().now().seconds()-this->start_time) > WAITING_TIMEOUT)
    {
        this->waiting_timeout = true;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Drone not ready");
    }
}
void PreparingStateManager::openBoxAndClamp()
{
    // Implement the logic for opening the box and starting the drone
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Opening box and starting drone");
    }
    state = PreparingState::OPEN_BOX_AND_CLAMP;
    if (this->change_state){
        std::thread([this](){
            // this->box_state_manager->power_button_cmd(1);
            if (this->box_state_manager->lid_cmd(1) && this->box_state_manager->clamp_cmd(0, 0, 0, 3))
            {
                this->send_cmd_open_box_and_clamp = 1;
                RCLCPP_INFO(this->box_state_manager->get_logger(), "Box opened and drone started");
            }
            else
            {
                this->send_cmd_open_box_and_clamp = 2;
                RCLCPP_INFO(this->box_state_manager->get_logger(), "Failed to open box and start drone");
            }
        }).detach();
    }
}
void PreparingStateManager::waitingBoxClampOpen()
{
    // Implement the logic for waiting for the box clamp to open
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Waiting for box clamp to open");
    }
    state = PreparingState::WAITING_BOX_CLAMP_OPEN;
    if(this->box_state_manager->lid_status_msg_.lid_status == dib_msgs::msg::LidStatus::OPENED && 
       this->box_state_manager->box_telemetry_msg_.box_info.clamp_state == dib_msgs::msg::BoxInfo::OPENED)
    {
        this->box_clamp_open = true;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Box clamp opened");
    }
    else if((rclcpp::Clock().now().seconds()-this->start_time) > WAITING_TIMEOUT)
    {
        this->waiting_timeout = true;
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Box clamp not opened");
    }
}
void PreparingStateManager::waitingReadyToFly()
{
    // Implement the logic for waiting for GPS to be ready
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Waiting for drone to be ready to fly");
    }
    state = PreparingState::WAITING_READY_TO_FLY;
}
void PreparingStateManager::done()
{
    // Implement the logic for done state
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Preparing state done");
    }
    state = PreparingState::DONE;
}
void PreparingStateManager::failed()
{
    // Implement the logic for failed state
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Preparing state failed");
    }
    state = PreparingState::FAILED;
}

