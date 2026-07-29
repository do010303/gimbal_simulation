#ifndef DIAGNOSTICS_HPP
#define DIAGNOSTICS_HPP
#include <chrono>
#include <functional>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "dib_msgs/msg/box_telemetry.hpp"
#include "dib_msgs/msg/box_environment.hpp"
#include "dib_msgs/msg/box_state.hpp"
#include "dib_msgs/msg/box_info.hpp"
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
#include "dib_msgs/msg/clamp_status.hpp"


#endif
