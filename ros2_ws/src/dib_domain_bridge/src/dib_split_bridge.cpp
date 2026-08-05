// Split-domain bridge for drone-in-a-box M4: bridges ONLY the 3 contract
// interfaces between the box domain and the drone domain, using domain_bridge.
//
//   box(BOX_DOMAIN)     --b2/telemetry-->     drone(DRONE_DOMAIN)
//   drone(DRONE_DOMAIN) --d1/telemetry-->     box    (BEST_EFFORT/VOLATILE)
//   drone(DRONE_DOMAIN) --b2/drone_cmd-->     box    (REQUEST_LANDING/TURN_OFF_DRONE)
//   box(BOX_DOMAIN)     --/dock/drone_power--> drone (SITL fixture, TRANSIENT_LOCAL)
//
// FALLBACK BRIDGE. The default M4 bridge is DDS-Router 2.2.0 (see
// precision_landing/config/dds_router_split.yaml). Keep this one working as a
// second option: it installs from apt (`ros-humble-domain-bridge`) instead of
// a ~4 min source build, so it is the faster path when DDS-Router is not set
// up on a machine, and it is ROS-native so it also bridges SERVICES if the
// contract ever needs one again.
//
// All three interfaces are TOPICS. b2/drone_cmd used to be the b2/cmd SERVICE;
// it moved to a topic because DDS-Router never routes a service reply across
// domains, and the reply was dead weight anyway (box_state_manager set
// success=true before doing any work — telemetry was always the real
// confirmation). box_state_manager still serves b2/cmd for the operator/server
// role; that role just does not cross the domain boundary.
//
// Domains come from args: dib_split_bridge <box_domain> <drone_domain>
#include <cstdlib>
#include <rclcpp/rclcpp.hpp>
#include "domain_bridge/domain_bridge.hpp"
#include "domain_bridge/topic_bridge_options.hpp"
#include "domain_bridge/qos_options.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  size_t box_domain = 42, drone_domain = 0;
  if (argc >= 3) { box_domain = std::atoi(argv[1]); drone_domain = std::atoi(argv[2]); }

  domain_bridge::DomainBridge bridge;

  // box_state telemetry: box -> drone
  bridge.bridge_topic("b2/telemetry", "dib_msgs/msg/BoxTelemetry", box_domain, drone_domain);

  // drone telemetry: drone -> box (publisher is BEST_EFFORT / VOLATILE)
  domain_bridge::TopicBridgeOptions d1opts;
  d1opts.qos_options(domain_bridge::QosOptions()
      .reliability(rclcpp::ReliabilityPolicy::BestEffort)
      .durability(rclcpp::DurabilityPolicy::Volatile));
  bridge.bridge_topic("d1/telemetry", "dib_msgs/msg/DroneTelemetry", drone_domain, box_domain, d1opts);

  // drone commands: drone -> box. Publisher is BoxLink (precision_landing),
  // subscriber is box_state_manager::drone_cmd_callback. Default QoS both
  // ends (depth 10, RELIABLE/VOLATILE), so no qos_options override here.
  bridge.bridge_topic("b2/drone_cmd", "dib_msgs/msg/BoxCmd", drone_domain, box_domain);

  // SITL FIXTURE, not part of the contract -- drop this on real hardware.
  // /dock/drone_power stands in for the dock power rail. On real hardware the
  // box cutting power kills the drone's computer, so d1/telemetry stops for
  // free. In SITL MAVROS keeps running, so box_hardware_adapter publishes this
  // flag and mavros_to_dib_telemetry stops publishing when it goes false. The
  // box only leaves POWER_OFF -> DONE -> CHARGING once d1/telemetry has been
  // stale for 5 s (securing_state_manager.cpp). Without this hop across the
  // domain split, the box HANGS at POWER_OFF and never reaches CHARGING.
  // Publisher is TRANSIENT_LOCAL so a late subscriber still learns the state.
  domain_bridge::TopicBridgeOptions pwropts;
  pwropts.qos_options(domain_bridge::QosOptions()
      .reliability(rclcpp::ReliabilityPolicy::Reliable)
      .durability(rclcpp::DurabilityPolicy::TransientLocal));
  bridge.bridge_topic("/dock/drone_power", "std_msgs/msg/Bool", box_domain, drone_domain, pwropts);

  RCLCPP_INFO(rclcpp::get_logger("dib_split_bridge"),
      "bridging b2/telemetry(%zu->%zu) d1/telemetry(%zu->%zu) b2/drone_cmd(%zu->%zu) "
      "/dock/drone_power(%zu->%zu, SITL fixture)",
      box_domain, drone_domain, drone_domain, box_domain, drone_domain, box_domain,
      box_domain, drone_domain);

  rclcpp::executors::SingleThreadedExecutor executor;
  bridge.add_to_executor(executor);
  executor.spin();
  rclcpp::shutdown();
  return 0;
}
