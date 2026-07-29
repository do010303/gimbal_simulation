#include "scheduler.hpp"
#include <filesystem>
#include <fstream>
#include <thread>

namespace fs = std::filesystem;



uint32_t get_time_start(std::string file_name)
{
  size_t underscore_pos = file_name.find('_');
    if (underscore_pos == std::string::npos) {
        throw std::invalid_argument("Invalid filename format: missing '_'");
    }

    std::string time_str = file_name.substr(0, underscore_pos);
    return static_cast<uint32_t>(std::stoul(time_str));
}


void Scheduler::boxStateCallback(const dib_msgs::msg::BoxState::SharedPtr msg)
{
  this->box_state_msg_ = *msg;
}

Scheduler::Scheduler() : Node("scheduler")
{
    // Declare parameters
    this->declare_parameter("box_id", 1);
    this->declare_parameter("mission_schedule_folder_path", "/home/ws/src/box_manager/schedules");
    this->box_id_ = this->get_parameter("box_id").as_int();
    this->mission_schedule_folder_path_ = this->get_parameter("mission_schedule_folder_path").as_string();

    if (!fs::exists(this->mission_schedule_folder_path_)) {
      if (!fs::create_directories(this->mission_schedule_folder_path_)) {
        throw std::runtime_error("Failed to create directory: " + this->mission_schedule_folder_path_);
      }
    }



    // Create service
    mission_schedule_cmd_service_ = this->create_service<dib_msgs::srv::MissionScheduleCmd>(
        "b" + std::to_string(this->box_id_) + "/mission_schedule/cmd",
        std::bind(&Scheduler::missionScheduleCmdCallback, this, std::placeholders::_1, std::placeholders::_2));

    box_state_sub_ = this->create_subscription<dib_msgs::msg::BoxState>("box/state", 10, std::bind(&Scheduler::boxStateCallback, this, std::placeholders::_1));

    // Create client
    mission_upload_client_ = this->create_client<dib_msgs::srv::MissionUpload>("box/mission_upload");
    // Create timer
    scheduler_state_timer_ = this->create_wall_timer(200ms, std::bind(&Scheduler::state_machine_timer_callback, this));
}

Scheduler::~Scheduler()
{
}

void Scheduler::missionScheduleCmdCallback(const std::shared_ptr<dib_msgs::srv::MissionScheduleCmd::Request> request,
                                            std::shared_ptr<dib_msgs::srv::MissionScheduleCmd::Response> response)
{
    RCLCPP_INFO(this->get_logger(), "Received mission schedule command");

    // Check if the command is valid
    response->accepted = true;
    switch (request->command)
    {
    case dib_msgs::msg::MissionScheduleCmd::SET_MISSION_SCHEDULE:
      /* code */
      // saveMissionSchedule(request->mission_schedule);
      if( request->mission_schedule.start_time.size() != 0)
      {
        RCLCPP_INFO(this->get_logger(), "Start time size: %ld", request->mission_schedule.start_time.size());
        saveToYAML(request->mission_schedule,request->mission_schedule.start_time.at(0));
      }
      else response->accepted = false; 
      break;
    case dib_msgs::msg::MissionScheduleCmd::GET_MISSION_SCHEDULE:
      response->mission_schedules = loadAllMissionSchedules(this->mission_schedule_folder_path_);
      break;
    case dib_msgs::msg::MissionScheduleCmd::DELETE_MISSION_SCHEDULE:
      if(deleteMissionFileById(this->mission_schedule_folder_path_,request->mission_schedule.id))
      {
        response->accepted = true;
        response->message = "Mission schedule deleted successfully.";
      }
      else
      {
        response->accepted = false;
        response->message = "Failed to delete mission schedule.";
      }

      break;
    default:
      RCLCPP_INFO(this->get_logger(),"Command is invalid");
      break;
    }
}

SchedulerState Scheduler::checkNewState(SchedulerState state){
  SchedulerState new_state = state;
  std::vector<std::string> list_file;
  switch (state)
  {
    case SchedulerState::CHECK_SCHEDULE:
    /* code */
      list_file = listYamlFiles(this->mission_schedule_folder_path_);
      for(std::string file: list_file)
      {
        if(rclcpp::Clock().now().seconds() > get_time_start(file))
        {
          this->file_name = file;
          new_state = SchedulerState::GET_MISSION;
        }
      }
    break;
  case SchedulerState::GET_MISSION:
    /* code */
    if(this->box_state_msg_.state == dib_msgs::msg::BoxState::IDLE){
      if(rclcpp::Clock().now().seconds() - get_time_start(this->file_name) > 10) new_state = SchedulerState::SAVE_NEW_SCHEDULE;
      else new_state = SchedulerState::UPLOAD_MISSION;
    }
    else new_state = SchedulerState::SAVE_NEW_SCHEDULE;
    break;
  case SchedulerState::UPLOAD_MISSION:
    /* code */
    new_state = SchedulerState::SAVE_NEW_SCHEDULE;
    break;
  case SchedulerState::SAVE_NEW_SCHEDULE:
    /* code */
    new_state = SchedulerState::CHECK_SCHEDULE;   
    break;
  default:
    break;
  }
  return new_state;
}

void Scheduler::runStateMachine(SchedulerState state){
  this->scheduler_state_ = state;
  switch (this->scheduler_state_)
  {
  case SchedulerState::CHECK_SCHEDULE:
    /* code */
    checkSchedule();
    break;
  case SchedulerState::GET_MISSION:
    /* code */
    getMission();
    break;
  case SchedulerState::UPLOAD_MISSION:
    /* code */
    uploadMission();
    break;
  case SchedulerState::SAVE_NEW_SCHEDULE:
    /* code */
    saveNewSchedule();
    break;
  default:
    break;
  }
}


void Scheduler::checkSchedule()
{
  RCLCPP_INFO(this->get_logger(),"In Check schedule");
}

void Scheduler::getMission()
{
  RCLCPP_INFO(this->get_logger(),"In Get Mission");
  loadMissionScheduleFromFile(this->mission_schedule_folder_path_ + "/" + this->file_name, this->mission_schedule_msg_);
  RCLCPP_INFO(this->get_logger(),"Number of mission: %ld", this->mission_schedule_msg_.mission.size());
}

void Scheduler::loadMissionScheduleFromFile(std::string filepath, dib_msgs::msg::MissionSchedule& mission_schedule)
{
  YAML::Node root = YAML::LoadFile(filepath);
  mission_schedule.mission.clear();

  mission_schedule.id = root["id"].as<std::string>();
  
  const auto& start_time = root["start_time"];

  for (const auto& time : start_time) {
      mission_schedule.start_time.push_back(time.as<int32_t>());
  }

  const YAML::Node& mission = root["mission"];
  for (const auto& item : mission) {
      dib_msgs::msg::MissionItem mission_item;
      mission_item.latitude = item["latitude"].as<double>();
      mission_item.longitude = item["longitude"].as<double>();
      mission_item.altitude = item["altitude"].as<double>();
      mission_item.command = item["command"].as<uint16_t>();
      mission_item.param1 = item["param1"].as<float>();
      mission_item.param2 = item["param2"].as<float>();
      mission_item.cam_id = item["cam_id"].as<uint8_t>();
      mission_item.cam_mode = item["cam_mode"].as<uint8_t>();
      mission_item.cam_interval = item["cam_interval"].as<float>();
      mission_item.cam_yaw = item["cam_yaw"].as<int16_t>();
      mission_item.cam_pitch = item["cam_pitch"].as<int16_t>();

      mission_schedule.mission.push_back(mission_item);
  }
}

void Scheduler::uploadMission()
{
  RCLCPP_INFO(this->get_logger(),"In Upload mission");
  std::thread([this]()
  {
    uploadMission(this->mission_schedule_msg_);
  }).detach();
}

void Scheduler::saveNewSchedule()
{
  RCLCPP_INFO(this->get_logger(),"In Save new schedule");
  deleteMissionFileByNameFile(this->mission_schedule_folder_path_,this->file_name);
  std::sort(this->mission_schedule_msg_.start_time.begin(), this->mission_schedule_msg_.start_time.end());
  for (const auto &time : this->mission_schedule_msg_.start_time) {
    if (rclcpp::Clock().now().seconds() < time) {
      saveToYAML(this->mission_schedule_msg_, time);
      break;
    }
  }
}

void Scheduler::saveToYAML(dib_msgs::msg::MissionSchedule & mission_schedule, int32_t time_start)
{
  // Kiểm tra tồn tại thư mục, nếu không thì tạo
  if (!fs::exists(this->mission_schedule_folder_path_)) {
    if (!fs::create_directories(this->mission_schedule_folder_path_)) {
      throw std::runtime_error("Failed to create directory: " + this->mission_schedule_folder_path_);
    }
  }

  // Tạo tên file theo định dạng (time_unix)_(mission_id).yaml
  std::string filename = std::to_string(time_start) + "_" + mission_schedule.id + ".yaml";
  std::string file_path = this->mission_schedule_folder_path_ + "/" + filename;

  YAML::Emitter out;
  out << YAML::BeginMap;
  out << YAML::Key << "id" << YAML::Value << mission_schedule.id;
  out << YAML::Key << "start_time" << YAML::Value << YAML::BeginSeq;
  for (const auto &time : mission_schedule.start_time) {
    out << time;
  }
  out << YAML::EndSeq;

  out << YAML::Key << "mission" << YAML::Value << YAML::BeginSeq;
  for (const auto &item : mission_schedule.mission) {
    out << YAML::BeginMap;
    out << YAML::Key << "latitude" << YAML::Value << item.latitude;
    out << YAML::Key << "longitude" << YAML::Value << item.longitude;
    out << YAML::Key << "altitude" << YAML::Value << item.altitude;
    out << YAML::Key << "command" << YAML::Value << item.command;
    out << YAML::Key << "param1" << YAML::Value << item.param1;
    out << YAML::Key << "param2" << YAML::Value << item.param2;
    out << YAML::Key << "cam_id" << YAML::Value << static_cast<int>(item.cam_id);
    out << YAML::Key << "cam_mode" << YAML::Value << static_cast<int>(item.cam_mode);
    out << YAML::Key << "cam_interval" << YAML::Value << item.cam_interval;
    out << YAML::Key << "cam_yaw" << YAML::Value << item.cam_yaw;
    out << YAML::Key << "cam_pitch" << YAML::Value << item.cam_pitch;

    out << YAML::EndMap;
  }
  out << YAML::EndSeq;
  out << YAML::EndMap;

  std::ofstream fout(file_path);
  if (!fout.is_open()) {
    throw std::runtime_error("Failed to open file for writing: " + file_path);
  }
  fout << out.c_str();
  fout.close();
}

uint8_t Scheduler::deleteMissionFileById(std::string& directory,std::string& mission_id)
{

    if (!fs::exists(directory) || !fs::is_directory(directory)) {
        RCLCPP_INFO(this->get_logger(),"Invalid directory: %s",directory.c_str());
        return 0;
    }

    for (const auto& entry : fs::directory_iterator(directory)) {
        if (entry.is_regular_file()) {
            auto path = entry.path();
            if (path.extension() == ".yaml") {
                std::string filename = path.filename().string();
                // Tìm mission_id ở sau dấu '_' và trước '.yaml'
                size_t underscore_pos = filename.find('_');
                size_t dot_pos = filename.rfind('.');
                if (underscore_pos != std::string::npos && dot_pos != std::string::npos) {
                    std::string id_in_filename = filename.substr(underscore_pos + 1, dot_pos - underscore_pos - 1);
                    if (id_in_filename == mission_id) {
                        fs::remove(path);
                        RCLCPP_INFO(this->get_logger(),"Deleted mission file: %s", file_name.c_str());
                        return 1;
                    }
                }
            }
        }
    }

    RCLCPP_INFO(this->get_logger(),"Mission file with ID '%s' not found in: %s",mission_id.c_str(),directory.c_str());
    return 0;
}

uint8_t Scheduler::deleteMissionFileByNameFile(std::string& directory,std::string& name_file)
{
    if (!fs::exists(directory) || !fs::is_directory(directory)) {
        RCLCPP_INFO(this->get_logger(),"Invalid directory: %s",directory.c_str());
        return 0;
    }
    for (const auto& entry : fs::directory_iterator(directory)) {
        if (entry.is_regular_file()) {
            auto path = entry.path();
            if (path.filename().string() == name_file) {
                fs::remove(path);
                RCLCPP_INFO(this->get_logger(),"Deleted mission file: %s", name_file.c_str());
                return 1;
            }
        }
    }
    RCLCPP_INFO(this->get_logger(),"Mission file '%s' not found in: %s",name_file.c_str(),directory.c_str());
    return 0;
}


std::vector<std::string> Scheduler::listYamlFiles(std::string directory_path) {

  std::vector<std::string> yaml_files;

  if (!fs::exists(directory_path) || !fs::is_directory(directory_path)) {
      throw std::runtime_error("Directory does not exist: " + directory_path);
  }

  for (const auto &entry : fs::directory_iterator(directory_path)) {
      if (entry.is_regular_file()) {
          auto path = entry.path();
          if (path.extension() == ".yaml" || path.extension() == ".yml") {
              yaml_files.push_back(path.filename().string());
          }
      }
  }
  // std::sort(yaml_files.begin(), yaml_files.end()); 
  return yaml_files;
}

std::vector<dib_msgs::msg::MissionSchedule> Scheduler::loadAllMissionSchedules(const std::string& dir_path)
{
  std::vector<dib_msgs::msg::MissionSchedule> missions;

    if (!fs::exists(dir_path) || !fs::is_directory(dir_path)) {
        std::cerr << "Invalid mission directory: " << dir_path << std::endl;
        return missions;
    }

    for (const auto& entry : fs::directory_iterator(dir_path)) {
        if (entry.is_regular_file() && entry.path().extension() == ".yaml") {
            try {
                YAML::Node root = YAML::LoadFile(entry.path().string());
                dib_msgs::msg::MissionSchedule mission_schedule;

                mission_schedule.id = root["id"].as<std::string>();

                const auto& start_time = root["start_time"];

                for (const auto& time : start_time) {
                    mission_schedule.start_time.push_back(time.as<int32_t>());
                }

                const YAML::Node& mission = root["mission"];
                for (const auto& item : mission) {
                    dib_msgs::msg::MissionItem mission_item;
                    mission_item.latitude = item["latitude"].as<double>();
                    mission_item.longitude = item["longitude"].as<double>();
                    mission_item.altitude = item["altitude"].as<double>();
                    mission_item.command = item["command"].as<uint16_t>();
                    mission_item.param1 = item["param1"].as<float>();
                    mission_item.param2 = item["param2"].as<float>();
                    mission_item.cam_id = item["cam_id"].as<uint8_t>();
                    mission_item.cam_mode = item["cam_mode"].as<uint8_t>();
                    mission_item.cam_interval = item["cam_interval"].as<float>();
                    mission_item.cam_yaw = item["cam_yaw"].as<int16_t>();
                    mission_item.cam_pitch = item["cam_pitch"].as<int16_t>();

                    mission_schedule.mission.push_back(mission_item);
                }

                missions.push_back(mission_schedule);
            } catch (const std::exception& e) {
                std::cerr << "Error loading " << entry.path() << ": " << e.what() << std::endl;
            }
        }
    }
    return missions;
}


void Scheduler::uploadMission(dib_msgs::msg::MissionSchedule & mission_schedule)
{
  RCLCPP_INFO(this->get_logger(), "Number: %ld",mission_schedule.mission.size());
  if(this->mission_upload_client_->wait_for_service(1s))
  {
      auto request = std::make_shared<dib_msgs::srv::MissionUpload::Request>();
      request->id = 1 + this->box_id_ * 10; 
      request->mission = mission_schedule.mission;
      RCLCPP_INFO(this->get_logger(), "Number: %ld",request->mission.size());
      auto result = this->mission_upload_client_->async_send_request(request);
      if (result.wait_for(5s) == std::future_status::ready) {
          auto response = result.get();
          if (response->success) {
              RCLCPP_INFO(this->get_logger(), "Mission upload success %ld",request->mission.size());
          } else {
              RCLCPP_ERROR(this->get_logger(), "Mission upload failed");
          }
      } else {
          RCLCPP_ERROR(this->get_logger(), "Failed to send mission upload");
      }
  }
  else
  {
      RCLCPP_ERROR(this->get_logger(), "Mission upload service not available");
  }
}

void Scheduler::state_machine_timer_callback()
{
  SchedulerState new_state = checkNewState(this->scheduler_state_);
  runStateMachine(new_state);
}

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    auto scheduler = std::make_shared<Scheduler>();
    rclcpp::spin(scheduler);
    rclcpp::shutdown();
    return 0;
}


