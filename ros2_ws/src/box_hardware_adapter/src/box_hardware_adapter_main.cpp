#include <memory>

#include <rclcpp/rclcpp.hpp>

#include "box_hardware_adapter/box_hardware_adapter_node.hpp"

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<BoxHardwareAdapterNode>());
  rclcpp::shutdown();
  return 0;
}
