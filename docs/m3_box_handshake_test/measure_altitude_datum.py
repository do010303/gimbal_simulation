#!/usr/bin/env python3
"""Measure the tracker's range estimate against ground truth, two ways at once.

WHY THIS EXISTS, AND WHY IT WAS REWRITTEN
The HUD shows `UAV ENU: U` next to `MARKER DIST` and they are never equal. Hand
interpolation of two log lines produced two wrong answers (0.64, then 0.787)
before the right one (0.52), so the first version of this script measured it
automatically instead.

That first version was still wrong, in a way worth recording so it is not
repeated. It compared

    uav_z                        a VERTICAL distance
    sqrt(tvec_x^2+tvec_y^2+tvec_z^2)   a SLANT range

Those are different quantities. The drone is 3.2 m horizontally from the box
when it climbs over the takeoff point, so the slant range there is a metre
longer than the vertical drop, and the difference between them changes
continuously through the flight. Their difference therefore has no fixed value
to converge on, and averaging it over a descent reports the mean of a trend --
a number that describes none of the samples. It printed `gap 0.889 +- 0.204`
against a prediction of 0.519 and called the 0.371 residual unexplained. There
was nothing to explain.

The verdict logic was unsound for the same reason: it compared sd(gap) against
sd(ratio) and declared whichever was smaller to be the cause. Those two have
different units and different scales, so the comparison decides nothing. It
reported "DATUM OFFSET" from data in which gap ranged 0.46 -> 1.03.

WHAT THIS MEASURES NOW
Two estimators that fail for different reasons, so agreement between them means
something:

  A. VERTICAL  gap_v = uav_z - tvec_z
     The gimbal holds nadir (three joint-position controllers, gimbal/model.sdf
     :315-345), so tvec_z is the vertical camera->marker distance whatever the
     horizontal offset. gap_v should be constant at

         marker height - camera height above base_link - z datum offset
         0.63673       - 0.118                         - (unknown)

     A CONSTANT gap means a datum offset. A gap that TRENDS with altitude means
     something range-dependent, and the report says which by testing the trend
     explicitly rather than eyeballing a standard deviation.

  B. HORIZONTAL  hypot(tvec_x, tvec_y)  vs  distance from MAVROS x,y to the
     known marker x,y. Both are magnitudes of horizontal vectors, so this is
     invariant to drone yaw and to camera mount yaw, and -- the point of it --
     it never touches z, so no datum offset can contaminate it. A least-squares
     slope of 1.0 means the tracker's SCALE is right. This is the decisive test
     for marker_size and camera intrinsics; A cannot separate those from a
     datum offset, and B is immune to the datum.

     B needs the marker's true position, which only exists in SITL. That is
     what makes the test possible here and impossible on hardware.

ALREADY RULED OUT, by direct measurement of the rendered marker rather than by
assumption -- do not re-suspect these without new evidence:

    marker.png outer black square  959 / 1197 px = 0.801170 of the plane
    plane 0.6241 m * 0.801170      = 0.50001 m   == marker_size: 0.50   OK
    fractal level 1  240 px = 0.2503 * outer     vs config 0.25         OK
    fractal level 2   60 px = 0.0626 * outer     vs config 0.0625       OK

USAGE
Run during a flight, alongside the normal stack, then Ctrl+C for the report:

    python3 docs/m3_box_handshake_test/measure_altitude_datum.py

Passive: subscribes only, publishes nothing, calls no service. A result here
cannot be an artefact of the harness stimulating the system.
"""

import math
import statistics
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

from geometry_msgs.msg import PoseStamped
from dib_msgs.msg import LandingTarget6D


# --- Ground truth from the simulation, not assumed -------------------------
# box_spawn_only.launch.py: MARKER_X/Y/Z, themselves derived from the box spawn
# so the two cannot drift apart. SITL ONLY -- on hardware there is no such
# number and test B below is not available.
MARKER_X = 2.5129
MARKER_Y = -2.5896
MARKER_Z = 0.63673
# x500_gimbal/model.sdf:9  gimbal at z=+0.28 relative to base_link
# gimbal/model.sdf:265     camera sensor at z=-0.162 within the gimbal
CAMERA_Z_ABOVE_BASE = 0.28 - 0.162          # +0.118
PREDICTED_GAP_V = MARKER_Z - CAMERA_Z_ABOVE_BASE

# Pair a pose with a target only if their stamps are closer than this. The gz
# image bridge adds ~40-60 ms, so anything beyond this is not the same instant.
MAX_PAIR_SKEW_S = 0.08

# Below this the horizontal offset is all noise: hypot() of two zero-mean
# errors is biased upward, which would drag the fitted intercept. Fit B only on
# samples with a real baseline.
MIN_H_FOR_FIT = 0.30

TRACKING = LandingTarget6D.TRACKING


class Sample:
    __slots__ = ('uav_z', 'h_true', 'h_meas', 'v_meas', 'skew')

    def __init__(self, uav_z, h_true, h_meas, v_meas, skew):
        self.uav_z = uav_z
        self.h_true = h_true
        self.h_meas = h_meas
        self.v_meas = v_meas
        self.skew = skew

    @property
    def gap_v(self):
        return self.uav_z - self.v_meas


class DatumMeasurer(Node):
    def __init__(self):
        super().__init__('measure_altitude_datum')

        best_effort = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=50,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE)

        self.poses = []     # (t, x, y, z)
        self.samples = []

        self.create_subscription(
            PoseStamped, '/mavros/local_position/pose', self.on_pose, best_effort)
        self.create_subscription(
            LandingTarget6D, '/landing/target_camera', self.on_target, best_effort)

        self.get_logger().info(
            'Measuring tracker range against ground truth. Fly, then Ctrl+C.\n'
            f'  A vertical  : expect uav_z - tvec_z = {MARKER_Z:.5f} - '
            f'{CAMERA_Z_ABOVE_BASE:.3f} = {PREDICTED_GAP_V:.3f} m minus the z datum offset\n'
            f'  B horizontal: expect slope 1.000 against marker at '
            f'({MARKER_X:.4f}, {MARKER_Y:.4f})')

    def on_pose(self, msg):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        p = msg.pose.position
        self.poses.append((t, p.x, p.y, p.z))
        # 5 s of history is plenty to find a match a few tens of ms away.
        while self.poses and (t - self.poses[0][0]) > 5.0:
            self.poses.pop(0)

    def on_target(self, msg):
        if msg.state != TRACKING:
            return
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if not self.poses:
            return
        # Nearest pose in time, not the newest -- the newest describes a later
        # instant than the frame this measurement came from.
        best = min(self.poses, key=lambda p: abs(p[0] - t))
        skew = abs(best[0] - t)
        if skew > MAX_PAIR_SKEW_S:
            return
        _, dx, dy, dz = best
        self.samples.append(Sample(
            uav_z=dz,
            h_true=math.hypot(dx - MARKER_X, dy - MARKER_Y),
            h_meas=math.hypot(msg.x, msg.y),
            v_meas=msg.z,
            skew=skew))


def linfit(xs, ys):
    """Least-squares y = a*x + b, plus R^2. Returns None if degenerate."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-9:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    a = sxy / sxx
    b = my - a * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 1e-9 else float('nan')
    resid = [y - (a * x + b) for x, y in zip(xs, ys)]
    return a, b, r2, statistics.pstdev(resid)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float('nan')
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-9 or syy <= 1e-9:
        return float('nan')
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def report(node):
    s = node.samples
    print('\n' + '=' * 74)
    print('  tracker range vs ground truth')
    print('=' * 74)

    if len(s) < 10:
        print(f'\nOnly {len(s)} matched samples -- not enough to conclude.')
        print('Was the drone tracking the marker? Check /landing/target_camera.')
        return 2

    skews = [x.skew for x in s]
    print(f'\n{len(s)} matched samples, pairing skew '
          f'{statistics.mean(skews)*1000:.0f} ms mean / {max(skews)*1000:.0f} ms max')
    print(f'altitude covered: {min(x.uav_z for x in s):.2f} .. '
          f'{max(x.uav_z for x in s):.2f} m')
    print(f'horizontal offset covered: {min(x.h_true for x in s):.2f} .. '
          f'{max(x.h_true for x in s):.2f} m\n')

    # Bin by altitude. A trend that a single mean would hide shows up here as a
    # column that walks, which is exactly what the previous version missed.
    print('  binned by altitude (this is where a trend becomes visible)')
    print(f'{"uav_z band":>14} {"n":>4} {"h_true":>8} {"h_meas":>8} '
          f'{"v_meas":>8} {"gap_v":>8}')
    print('-' * 60)
    lo = min(x.uav_z for x in s)
    hi = max(x.uav_z for x in s)
    nbins = 8
    width = (hi - lo) / nbins if hi > lo else 1.0
    for i in range(nbins):
        a0, a1 = lo + i * width, lo + (i + 1) * width
        bucket = [x for x in s if a0 <= x.uav_z < a1 or (i == nbins - 1 and x.uav_z == hi)]
        if not bucket:
            continue
        print(f'{a0:6.2f}..{a1:5.2f} {len(bucket):4d} '
              f'{statistics.mean([x.h_true for x in bucket]):8.3f} '
              f'{statistics.mean([x.h_meas for x in bucket]):8.3f} '
              f'{statistics.mean([x.v_meas for x in bucket]):8.3f} '
              f'{statistics.mean([x.gap_v for x in bucket]):8.3f}')

    # --- A. vertical ------------------------------------------------------
    gaps = [x.gap_v for x in s]
    g_mean, g_sd = statistics.mean(gaps), statistics.pstdev(gaps)
    trend = pearson([x.uav_z for x in s], gaps)
    fit_a = linfit([x.uav_z for x in s], gaps)

    print('\n' + '-' * 74)
    print('A. VERTICAL   gap_v = uav_z - tvec_z')
    print(f'   mean {g_mean:+.3f} m   sd {g_sd:.3f}   predicted {PREDICTED_GAP_V:+.3f} m')
    print(f'   correlation with altitude: {trend:+.3f}', end='')
    if abs(trend) > 0.5:
        print('   <-- TRENDS, so the mean above is the mean of a trend')
        if fit_a:
            print(f'   slope {fit_a[0]*100:+.1f} cm of gap per metre of altitude')
    else:
        print('   <-- flat, so the mean is meaningful')
        print(f'   z datum offset implied: {PREDICTED_GAP_V - g_mean:+.3f} m '
              '(EKF origin above ground)')

    # --- B. horizontal ----------------------------------------------------
    fit_pts = [(x.h_true, x.h_meas) for x in s if x.h_true >= MIN_H_FOR_FIT]
    print('\n' + '-' * 74)
    print('B. HORIZONTAL  hypot(tvec_x,tvec_y) vs true horizontal offset')
    print(f'   (independent of the z datum -- this is the SCALE test)')
    if len(fit_pts) < 10:
        print(f'   only {len(fit_pts)} samples with offset >= {MIN_H_FOR_FIT} m'
              ' -- fly a leg that approaches the box from a distance.')
        fit_b = None
    else:
        fit_b = linfit([p[0] for p in fit_pts], [p[1] for p in fit_pts])
        a, b, r2, rsd = fit_b
        print(f'   n={len(fit_pts)}   slope {a:.4f}   intercept {b:+.3f} m'
              f'   R2 {r2:.4f}   resid sd {rsd:.3f} m')

    # --- verdict ----------------------------------------------------------
    print('\n' + '-' * 74)
    print('Verdict:')
    if fit_b is not None:
        a = fit_b[0]
        if abs(a - 1.0) < 0.03:
            print(f'  SCALE IS GOOD: slope {a:.4f} is within 3% of 1.0.')
            print('  marker_size and the intrinsics are consistent with reality;')
            print('  the flare altitude is not at risk from a scale error.')
        else:
            err = (a - 1.0) * 100.0
            print(f'  SCALE ERROR: slope {a:.4f}, i.e. ranges are reported '
                  f'{err:+.1f}% off.')
            print('  Since the rendered marker was measured correct (see header),')
            print('  suspect the camera intrinsics rather than marker_size:')
            print('    compare /camera/camera_info K against the SDF horizontal_fov.')
    if abs(trend) > 0.5:
        print('  gap_v is NOT constant, so this is not a pure datum offset.')
        print('  Read the binned table above: if h_true also grows in the same')
        print('  bands, the camera is not holding nadir and tvec_z is picking up')
        print('  a horizontal component. Check the gimbal pitch command.')
    else:
        resid = g_mean - PREDICTED_GAP_V
        if abs(resid) < 0.05:
            print(f'  gap_v matches geometry within {abs(resid)*100:.0f} cm -- '
                  'nothing unexplained.')
        else:
            print(f'  gap_v is constant but {resid:+.3f} m from geometry: a pure')
            print('  DATUM OFFSET. /mavros/local_position/pose z is measured from')
            print('  the arming point, not the ground, and the drone arms sitting')
            print(f'  on its legs. Cross-check against TOUCHDOWN alt_agl: resting')
            print(f'  on the box floor it should read {MARKER_Z:.3f} m plus landing')
            print('  gear height, minus this same offset.')
    print('=' * 74 + '\n')
    return 0


def main():
    rclpy.init()
    node = DatumMeasurer()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        # Both Ctrl+C and SIGTERM must still print the report -- losing a whole
        # descent's worth of samples to the way the node was stopped would be a
        # silly way to waste a flight.
        pass
    code = report(node)
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    sys.exit(code)


if __name__ == '__main__':
    main()
