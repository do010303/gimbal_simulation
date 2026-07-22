#include <memory>

#include <rclcpp/rclcpp.hpp>

#include "precision_landing/mavros_to_dib_telemetry_node.hpp"

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<precision_landing::MavrosToDibTelemetryNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
