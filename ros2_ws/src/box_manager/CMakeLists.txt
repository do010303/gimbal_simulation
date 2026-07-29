cmake_minimum_required(VERSION 3.5)
project(box_manager)
# cmake_policy(SET CMP0148 OLD)
# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(yaml-cpp REQUIRED)
find_package(ament_cmake REQUIRED)
find_package(dib_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosidl_typesupport_cpp REQUIRED)

include_directories(include)

add_executable(box_state_manager_node src/box_state_manager.cpp src/preparing_state_manager.cpp src/securing_state_manager.cpp)
target_link_libraries(box_state_manager_node
  ${dib_msgs_LIBRARIES}
  ${rosidl_typesupport_cpp_LIBRARIES}
)
ament_target_dependencies(box_state_manager_node rclcpp dib_msgs sensor_msgs )


add_executable(scheduler_node src/scheduler.cpp)
target_link_libraries(scheduler_node yaml-cpp
  ${dib_msgs_LIBRARIES}
  ${rosidl_typesupport_cpp_LIBRARIES}
)

ament_target_dependencies(scheduler_node rclcpp dib_msgs yaml-cpp)

install(TARGETS box_state_manager_node 

  DESTINATION lib/${PROJECT_NAME}
)

install(TARGETS scheduler_node
  DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY
  launch
  config
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # uncomment the line when a copyright and license is not present in all source files
  #set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # uncomment the line when this package is not in a git repo
  #set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
