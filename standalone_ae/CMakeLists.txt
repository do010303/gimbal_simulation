cmake_minimum_required(VERSION 3.5)
project(standalone_ae)

# Default to C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)

# Executable target
add_executable(ae_analyzer ae_analyzer.cpp)

# Target dependencies
target_link_libraries(ae_analyzer
  ${OpenCV_LIBS}
)

# Ament dependencies mapping (for ROS2 headers & libraries)
ament_target_dependencies(ae_analyzer
  rclcpp
  sensor_msgs
  cv_bridge
)
