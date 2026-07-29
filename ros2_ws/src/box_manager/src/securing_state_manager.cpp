#include "securing_state_manager.hpp"
#include "box_state_manager.hpp"

#define TIME_OUT 60  // 90s


SecuringStateManager::SecuringStateManager(BoxStateManager* box_state_manager)
{
    this->box_state_manager = box_state_manager;
    this->state = SecuringState::NONE;
    RCLCPP_INFO(this->box_state_manager->get_logger(), "SecuringStateManager initialized");
}

void SecuringStateManager::checkPosition()
{
    // Implement the logic for checking the position
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Checking position");
    }
    state = SecuringState::CHECK_POSITION;
}

void SecuringStateManager::closeClampH()
{
    // Implement the logic for closing the horizontal clamp
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Closing horizontal clamp");
    }
    state = SecuringState::CLOSE_CLAPM_H;
    if (this->change_state){
        std::thread([this](){
            if(this->box_state_manager->clamp_cmd(0,this->box_state_manager->pos_clamp_h_close,0,1))
            {
                this->cmd_success = 1;
            }
            else
            {
                this->cmd_success = 2;
                RCLCPP_INFO(this->box_state_manager->get_logger(), "Failed to send command to close horizontal clamp");
            }
        }).detach();
    }
}

void SecuringStateManager::closeClampV()
{
    // Implement the logic for closing the vertical clamp
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Closing vertical clamp");
    }
    state = SecuringState::CLOSE_CLAPM_V;
    if (this->change_state){
        std::thread([this](){
            if(this->box_state_manager->clamp_cmd(0,0,this->box_state_manager->pos_clamp_v_close,2))
            {
                this->cmd_success = 1;
            }
            else
            {
                this->cmd_success = 2;
                RCLCPP_INFO(this->box_state_manager->get_logger(), "Failed to send command to close vertical clamp");
            }
        }).detach();
    }
}
void SecuringStateManager::powerOff()
{
    // Implement the logic for powering off the drone
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Powering off drone");
    }
    state = SecuringState::POWER_OFF;
    if (this->change_state){
        std::thread([this](){
            if (this->box_state_manager->power_button_cmd(0))
            {
                this->cmd_success = 1;
            }
            else
            {
                this->cmd_success = 2;
                RCLCPP_INFO(this->box_state_manager->get_logger(), "Failed to send command to power off drone");
            }
        }).detach();
    }
}
void SecuringStateManager::closeLid()
{
    // Implement the logic for closing the lid
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Closing lid");
    }
    state = SecuringState::CLOSE_LID;
    if (this->change_state){
        std::thread([this](){
            if(this->box_state_manager->lid_cmd(0))
            {
                this->cmd_success = 1;
            }
            else
            {
                this->cmd_success = 2;
                RCLCPP_INFO(this->box_state_manager->get_logger(), "Failed to send command to close lid");
            }
        }).detach();
    }
}

void SecuringStateManager::waitingDroneRequestPowerOff()
{
    // Implement the logic for waiting for the drone to request power off
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Waiting for drone to request power off");
    }
    state = SecuringState::WAITING_DRONE_REQUEST_POWER_OFF;
}

void SecuringStateManager::done()
{
    // Implement the logic for when the process is done
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Process done");
    }
    state = SecuringState::DONE;
}

void SecuringStateManager::none()
{
    // Implement the logic for when the process is in none state
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Process in NONE state");
    }
    this->cmd_success = 0;
}

void SecuringStateManager::failed()
{
    // Implement the logic for when the process fails
    if (this->change_state) {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "Process failed");
    }
    state = SecuringState::FAILED;
}

void SecuringStateManager::runStateMachine(SecuringState new_state)
{
    if(this->state != new_state)
    {
        RCLCPP_INFO(this->box_state_manager->get_logger(), "SecuringStateManager state changed from %d to %d", (int)this->state, (int)new_state);
        this->start_time = rclcpp::Clock().now().seconds();
        this->state = new_state;
        this->change_state = true;
        this->cmd_success = 0;
       
    }
    else this->change_state = false;
    switch (new_state)
    {
        case SecuringState::NONE:
            this->cmd_success = 0;
            break;  
        case SecuringState::CHECK_POSITION:
            checkPosition();
            break;
        case SecuringState::CLOSE_CLAPM_H:
            closeClampH();
            break;
        case SecuringState::CLOSE_CLAPM_V:
            closeClampV();
            break;
        case SecuringState::CLOSE_LID:
            closeLid();
            break;
        case SecuringState::WAITING_DRONE_REQUEST_POWER_OFF:
            waitingDroneRequestPowerOff();
            break;
        case SecuringState::POWER_OFF:
            powerOff();
            break;
        case SecuringState::DONE:
            done();
            break;
        case SecuringState::FAILED:
            failed();
            break;
    }
}

SecuringState SecuringStateManager::checkNewState(SecuringState state)
{
    SecuringState new_state = state;
    switch (state)
    {
        case SecuringState::NONE:
            if(this->box_state_manager->box_state_ == BoxState::SECURING_DRONE){
                new_state = SecuringState::CHECK_POSITION;
            }
            break;
        case SecuringState::CHECK_POSITION:
            new_state = SecuringState::CLOSE_CLAPM_H;
            break;
        case SecuringState::CLOSE_CLAPM_H:
            if(this->box_state_manager->clamp_status_msg_.clamp_h_pos == this->box_state_manager->pos_clamp_h_close){
                new_state = SecuringState::CLOSE_CLAPM_V;
            }
            if(rclcpp::Clock().now().seconds()-this->start_time > TIME_OUT || this->cmd_success == 2){
                new_state = SecuringState::FAILED;
            }
            break;
        case SecuringState::CLOSE_CLAPM_V:
            if(this->box_state_manager->clamp_status_msg_.clamp_v_pos == this->box_state_manager->pos_clamp_v_close){
                new_state = SecuringState::CLOSE_LID;
            }
            if(rclcpp::Clock().now().seconds()-this->start_time > TIME_OUT || this->cmd_success == 2){
                new_state = SecuringState::FAILED;
            }
            break;
        case SecuringState::CLOSE_LID:
            if (this->box_state_manager->lid_status_msg_.lid_status == dib_msgs::msg::LidStatus::CLOSED){
                new_state = SecuringState::WAITING_DRONE_REQUEST_POWER_OFF;
            }
            if (rclcpp::Clock().now().seconds()-this->start_time > TIME_OUT || this->cmd_success == 2){
                new_state = SecuringState::FAILED;
            }
            break;
        case SecuringState::WAITING_DRONE_REQUEST_POWER_OFF:
            if (this->box_state_manager->request_poweroff){
                new_state = SecuringState::POWER_OFF;
                this->box_state_manager->request_poweroff = false;
            }
            if(rclcpp::Clock().now().seconds() - this->box_state_manager->drone_telemetry_msg_.header.stamp.sec > 5){
                new_state = SecuringState::DONE;
            }
            break;
        case SecuringState::POWER_OFF:
            if(rclcpp::Clock().now().seconds() - this->box_state_manager->drone_telemetry_msg_.header.stamp.sec > 5){
                new_state = SecuringState::DONE;
            }
            if (rclcpp::Clock().now().seconds()-this->start_time > TIME_OUT || this->cmd_success == 2){
                new_state = SecuringState::FAILED;
            }
            break;
        case SecuringState::DONE:
            new_state = SecuringState::NONE;
            break;
        case SecuringState::FAILED:
            new_state = SecuringState::NONE;
            break;
    }
    return new_state;
}


