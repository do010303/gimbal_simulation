#!/usr/bin/env python3
"""
SITL fixture: publish the box's GPS position on /gps.

WHY THIS EXISTS
box_state_manager subscribes to `gps` (sensor_msgs/NavSatFix) and derives
box_info.latitude/longitude from it (box_state_manager.cpp:68,187-194). In SITL
nothing publishes that topic -- the box_simulation `navsat` sensor has no
ros_gz_bridge (known gap recorded in the M2 section of TEST_PLAN_RESULTS.md).

Without this node box_info.latitude/longitude stay 0.0, and the drone's
st_goto_box() computes `dlat = 0.0 - 47.39...` -> a setpoint several thousand
kilometres away. The drone flies off instead of approaching the box. This is a
hard blocker for the 7b closed-loop test, not a cosmetic issue.

The coordinates below are the ACTUAL pad position in the SITL world, derived
(not guessed) from:
  Tools/simulation/gz/worlds/fractal_aruco_landing.sdf
    <spherical_coordinates> lat 47.397971057728974 lon 8.546163739800146
    <include> dib_box_landing_pad  <pose>4.0 -3.5 0 0 0 0</pose>   (ENU: E, N)

  dlat = -3.5 / R * 180/pi
  dlon =  4.0 / (R * cos(lat0)) * 180/pi      R = 6378137.0

NOTE box_state_manager then adds its antenna offset (x_anten_gps_offset=-0.15,
y_anten_gps_offset=1.9) on top of this, so box_info lands ~1.9 m north of the
pad centre. That is well inside goto_box_arrival_radius (3.0 m), and the visual
landing takes over from there, so it is harmless. Do not "fix" it by fudging
these numbers -- change the offsets in box_state_manager.yaml if it ever matters.
"""

import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix

# --- world constants (fractal_aruco_landing.sdf) ---
WORLD_LAT0 = 47.397971057728974
WORLD_LON0 = 8.546163739800146
EARTH_R = 6378137.0

# M3.5: the static dib_box_landing_pad was removed from the world; the marker
# now sits on the articulated box spawned by box_spawn_only.launch.py. These
# are the marker's world coordinates, derived from the spawn pose plus the
# marker's placement inside box.xacro:
#
#   spawn            (2.5, -2.0, 0.78233) with roll = pi/2
#   marker in model  (0.0129, -0.1456, 0.5896)
#   model -> world   (x, y, z) -> (x, -z, y)
#   => marker world  (2.5129, -2.5896, 0.6367)
#
# VERIFY THIS BY MEASURING in Gazebo rather than trusting the arithmetic: the
# model frame is rotated and that same conversion has already produced one
# wrong conclusion (see the antenna-offset note in docs/m3.md). If the
# measured position differs, trust the measurement and update these two
# numbers -- the fixture must follow the marker, never the other way round.
PAD_EAST = 2.5129
PAD_NORTH = -2.5896

PAD_LAT = WORLD_LAT0 + (PAD_NORTH / EARTH_R) * 180.0 / math.pi
PAD_LON = WORLD_LON0 + (PAD_EAST / (EARTH_R * math.cos(math.radians(WORLD_LAT0)))) * 180.0 / math.pi
PAD_ALT = 488.0   # unused for lat/lon; box_state_manager only reads N/E

PUBLISH_HZ = 5.0


class BoxGpsPublisher(Node):
    def __init__(self):
        super().__init__('box_gps_publisher')
        # Relative name 'gps' -> matches box_state_manager's own relative
        # subscription, so both resolve the same way under any namespace.
        self.pub = self.create_publisher(NavSatFix, 'gps', 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            f'Publishing box GPS on /gps at {PUBLISH_HZ:.0f} Hz: '
            f'lat={PAD_LAT:.9f} lon={PAD_LON:.9f} '
            f'(marker at ENU {PAD_EAST}, {PAD_NORTH} in fractal_aruco_landing)')

    def tick(self):
        msg = NavSatFix()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'gps_box'
        msg.latitude = PAD_LAT
        msg.longitude = PAD_LON
        msg.altitude = PAD_ALT
        msg.status.status = 0      # STATUS_FIX
        msg.status.service = 1     # SERVICE_GPS
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = BoxGpsPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
