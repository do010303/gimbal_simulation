cmake_minimum_required(VERSION 3.5)
project(box_hardware_adapter)

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(dib_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(trajectory_msgs REQUIRED)
find_package(std_msgs REQUIRED)

include_directories(include)

add_executable(box_hardware_adapter_node
  src/box_hardware_adapter_node.cpp
  src/box_hardware_adapter_main.cpp
)
ament_target_dependencies(box_hardware_adapter_node
  rclcpp
  dib_msgs
  sensor_msgs
  trajectory_msgs
  std_msgs
)

install(TARGETS box_hardware_adapter_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  config
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
