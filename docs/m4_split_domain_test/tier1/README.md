# Tier-1 bridge check — no Gazebo, 3 terminals, ~20s

Proves the M4 bridge carries all 3 contract interfaces WITHOUT running
PX4/Gazebo. Two fake nodes stand in for the box and drone computers; the real
bridge sits between them, using the **real project config**. Use this whenever
you want to confirm the bridge works before (or instead of) a full 7-terminal
run.

## Header (every terminal)
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
```

## Terminals

Đường dẫn tuyệt đối nên chạy từ thư mục nào cũng được. Bật C (cầu) trước, rồi
A và B — thứ tự không bắt buộc, nhưng cầu lên trước thì đỡ vài giây chờ
discovery.

| T | Domain export | Command |
|---|---|---|
| A (box)   | `export ROS_DOMAIN_ID=42` | `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m4_split_domain_test/tier1/box_side.py` |
| B (drone) | `export ROS_DOMAIN_ID=0`  | `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m4_split_domain_test/tier1/drone_side.py` |
| C (bridge)| *(none — bridge takes both domains itself)* | see below |

**C, bridge mặc định (DDS-Router):**
```bash
cd ~/DDS-Router-2.2 && source install/setup.bash
./install/ddsrouter_tool/bin/ddsrouter -c \
  ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/precision_landing/config/dds_router_split.yaml
```

**C, bridge dự phòng (domain_bridge):**
```bash
ros2 run dib_domain_bridge dib_split_bridge 42 0    # arg1=box domain, arg2=drone domain
```

## PASS looks like

Terminal B (drone) — box telemetry arrives, commands go out every 3 s:
```
>>> /b2/telemetry ARRIVED over bridge: box_state=9 box_id=2  (bridge box->drone OK)
<<< published /b2/drone_cmd #1: REQUEST_LANDING agent_id=12  (check the BOX terminal for arrival)
```

Terminal A (box) — each command lands, decoded:
```
>>> /b2/drone_cmd #1 ARRIVED over bridge: REQUEST_LANDING (command=23 agent_id=12 drone_id=1)  (bridge drone->box OK)
```

Third interface (`/d1/telemetry`, drone → box) has no console line — check it
from a 4th terminal on domain 42:
```bash
export ROS_DOMAIN_ID=42
python3 -c "
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from dib_msgs.msg import DroneTelemetry
rclpy.init(); n = rclpy.create_node('d1_check')
q = QoSProfile(depth=1); q.reliability=ReliabilityPolicy.BEST_EFFORT
q.durability=DurabilityPolicy.VOLATILE; q.history=HistoryPolicy.KEEP_LAST
got=[]; n.create_subscription(DroneTelemetry, '/d1/telemetry', lambda m: got.append(m), q)
end = n.get_clock().now().nanoseconds/1e9 + 8
while n.get_clock().now().nanoseconds/1e9 < end and not got: rclpy.spin_once(n, timeout_sec=0.3)
print('system_status=' + str(got[0].state.system_status) if got else 'NOTHING RECEIVED')
rclpy.shutdown()"
# -> system_status=111
```
`ros2 topic echo` is deliberately NOT used here: its auto-QoS path goes through
the ros2cli daemon's XML-RPC graph cache, which hangs or throws
`xmlrpc.client.Fault: !rclpy.ok()` on cross-domain topics even when the bridge
is working fine. A plain rclpy subscriber has no daemon dependency and is what
the real C++ nodes do anyway.

## FAIL / causal check

Kill terminal C (the bridge) while A and B keep running. Terminal B must keep
publishing (`#6`, `#7`, …) while terminal A **stops receiving** — the drone is
still talking, the messages just no longer cross. That is the proof the flow
goes through the bridge and is not domain leakage.

If A never prints "ARRIVED":
- bridge not running → `pgrep -af "ddsrouter|dib_split_bridge"`
- domain export wrong → A must be 42, B must be 0, C neither
- (DDS-Router only) custom type missing from the allowlist → every `dib_msgs`
  topic needs an explicit `name` + `type` entry in `dds_router_split.yaml`; the
  no-allowlist "bridge everything" mode silently carries nothing for custom
  types. `rt/b2/drone_cmd` → `dib_msgs::msg::dds_::BoxCmd_`.

## Kết quả

**PASS 2026-08-05** — DDS-Router 2.2.0 với `dds_router_split.yaml` thật:

| Giao diện | Hướng | Bằng chứng |
|---|---|---|
| `/b2/telemetry` | box 42 → drone 0 | `ARRIVED ... box_state=9 box_id=2` |
| `/b2/drone_cmd` | drone 0 → box 42 | 7/7 lệnh tới, `REQUEST_LANDING agent_id=12` |
| `/d1/telemetry` | drone 0 → box 42 | `system_status=111` (giữ đúng BEST_EFFORT) |

Nhân quả: tắt router → drone vẫn publish `#6`,`#7` nhưng box dừng nhận sau `#5`.

**Cầu dự phòng cũng PASS 2026-08-05** — cùng bộ script, đổi T7 sang
`dib_split_bridge 42 0`: `b2/telemetry` tới drone, 6/6 `REQUEST_LANDING` tới
box. Node cầu in `bridging b2/telemetry(42->0) d1/telemetry(0->42) b2/drone_cmd(0->42)`.
