#ifndef SCHEDULER_HPP
#define SCHEDULER_HPP

#include <yaml-cpp/yaml.h>

#include <chrono>
#include <functional>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "dib_msgs/srv/mission_schedule_cmd.hpp"
#include "dib_msgs/srv/mission_upload.hpp"
#include "dib_msgs/msg/mission_schedule.hpp"
#include "dib_msgs/msg/mission_schedule_cmd.hpp"
#include "dib_msgs/msg/box_state.hpp"


using namespace std::chrono_literals;


enum class SchedulerState
{
    CHECK_SCHEDULE = 0,
    GET_MISSION,
    UPLOAD_MISSION,
    SAVE_NEW_SCHEDULE
};


class Scheduler : public rclcpp::Node
{
    public:
        Scheduler();
        ~Scheduler();

    private:
        
        rclcpp::Service<dib_msgs::srv::MissionScheduleCmd>::SharedPtr mission_schedule_cmd_service_;

        rclcpp::Client<dib_msgs::srv::MissionUpload>::SharedPtr mission_upload_client_;

        rclcpp::Subscription<dib_msgs::msg::BoxState>::SharedPtr box_state_sub_;

        void missionScheduleCmdCallback(const std::shared_ptr<dib_msgs::srv::MissionScheduleCmd::Request> request,
                                        std::shared_ptr<dib_msgs::srv::MissionScheduleCmd::Response> response);
        void boxStateCallback(const dib_msgs::msg::BoxState::SharedPtr msg);

        void saveMissionSchedule(const dib_msgs::msg::MissionSchedule & mission_schedule);
        void saveToYAML(dib_msgs::msg::MissionSchedule & mission_schedule, int32_t time_start);
        void uploadMission(dib_msgs::msg::MissionSchedule & mission_schedule);
        void loadMissionScheduleFromFile(std::string filepath, dib_msgs::msg::MissionSchedule& mission_schedule);
        uint8_t deleteMissionFileById(std::string& directory,std::string& mission_id);
        uint8_t deleteMissionFileByNameFile(std::string& directory,std::string& name_file);
        std::vector<dib_msgs::msg::MissionSchedule> loadAllMissionSchedules(const std::string& dir_path);

        SchedulerState checkNewState(SchedulerState state);
        void runStateMachine(SchedulerState state);

        void state_machine_timer_callback();

        void checkSchedule();
        void getMission();
        void uploadMission();
        void saveNewSchedule();

        std::vector<std::string> listYamlFiles(std::string directory_path);
        
        rclcpp::TimerBase::SharedPtr scheduler_state_timer_;
        SchedulerState scheduler_state_;

        dib_msgs::msg::MissionSchedule mission_schedule_msg_;
        uint64_t box_id_;
        std::string file_name;
        std::string mission_schedule_folder_path_;
        dib_msgs::msg::BoxState box_state_msg_;

    
};




#endif // SCHEDULER_HPP