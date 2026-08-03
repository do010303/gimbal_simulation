#!/usr/bin/env python3
"""
SITL fixture: publish the box's ENVIRONMENT sensors (REQ_BOX_FEA_0003).

WHY THIS EXISTS
box_state_manager already assembles box_environment from these topics
(box_state_manager.cpp:57-62): env/outside/wind, env/outside/temperature,
system1/temperature2, system1/humidity1, env/outside/humidity, env/outside/rain.
In SITL there is NO weather sensor in the Gazebo world, so nothing publishes
them and box_environment stays all-zero. This fixture feeds plausible constant
values so the telemetry carries a full BoxEnvironment, the same way
box_gps_publisher.py feeds the GPS the world also lacks.

NOTE: these are SIMULATED values, not measured. Real weather sensing is a
hardware/HIL concern; in SITL this only proves the telemetry pipeline and
message structure, which is what REQ_BOX_FEA_0003 asks for at this level.

Topic names are RELATIVE (no leading '/') to match box_state_manager's own
relative subscriptions, so both resolve the same under any namespace.
"""
import rclpy
from rclpy.node import Node
from dib_msgs.msg import WindSensor, Temperature, Humidity, Rain

PUBLISH_HZ = 2.0

# Plausible fair-weather constants (simulated).
WIND_SPEED = 5.0        # km/h
WIND_DIRECTION = 90.0   # deg
INSIDE_TEMP = 25.0      # C  (box interior, AC-held)
OUTSIDE_TEMP = 31.0     # C
INSIDE_HUM = 45.0       # %
OUTSIDE_HUM = 70.0      # %
RAIN = False


class BoxEnvPublisher(Node):
    def __init__(self):
        super().__init__('box_env_publisher')
        self.wind = self.create_publisher(WindSensor, 'env/outside/wind', 10)
        self.temp_out = self.create_publisher(Temperature, 'env/outside/temperature', 10)
        self.temp_in = self.create_publisher(Temperature, 'system1/temperature2', 10)
        self.hum_in = self.create_publisher(Humidity, 'system1/humidity1', 10)
        self.hum_out = self.create_publisher(Humidity, 'env/outside/humidity', 10)
        self.rain = self.create_publisher(Rain, 'env/outside/rain', 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            f'Publishing SIMULATED box environment at {PUBLISH_HZ:.0f} Hz '
            f'(wind={WIND_SPEED} temp_in={INSIDE_TEMP} temp_out={OUTSIDE_TEMP} '
            f'hum_in={INSIDE_HUM} hum_out={OUTSIDE_HUM} rain={RAIN})')

    def tick(self):
        w = WindSensor(); w.wind_speed = WIND_SPEED; w.wind_direction = WIND_DIRECTION
        self.wind.publish(w)
        to = Temperature(); to.temperature = OUTSIDE_TEMP; self.temp_out.publish(to)
        ti = Temperature(); ti.temperature = INSIDE_TEMP; self.temp_in.publish(ti)
        hi = Humidity(); hi.humidity = INSIDE_HUM; self.hum_in.publish(hi)
        ho = Humidity(); ho.humidity = OUTSIDE_HUM; self.hum_out.publish(ho)
        r = Rain(); r.rain = RAIN; self.rain.publish(r)


def main():
    rclpy.init()
    node = BoxEnvPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
