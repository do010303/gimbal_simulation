# dib_domain_bridge

Cầu **dự phòng** cho M4 (tách domain box↔drone). Cầu mặc định là **DDS-Router
2.2.0** — xem `README.md` gốc, Phụ lục A.10.

Bắc cầu 3 giao diện hợp đồng + 1 fixture SITL, không hơn:

| Topic | Type | Chiều |
|---|---|---|
| `b2/telemetry` | `dib_msgs/msg/BoxTelemetry` | box → drone |
| `d1/telemetry` | `dib_msgs/msg/DroneTelemetry` | drone → box (BEST_EFFORT/VOLATILE) |
| `b2/drone_cmd` | `dib_msgs/msg/BoxCmd` | drone → box |
| `/dock/drone_power` | `std_msgs/msg/Bool` — **chỉ SITL** | box → drone (RELIABLE/TRANSIENT_LOCAL) |

`/dock/drone_power` giả lập đường điện dock: phần cứng thật cắt điện là máy
tính drone tắt nên `d1/telemetry` im ngay, còn SITL thì MAVROS vẫn chạy nên
phải báo bằng topic — `mavros_to_dib_telemetry` ngừng phát khi nhận `false`.
Box chỉ rời `POWER_OFF → DONE → CHARGING` khi `d1/telemetry` im quá 5 s, nên
**thiếu nó thì box kẹt ở `SECURING_DRONE`**. Bỏ dòng này khi chạy máy thật.

## Khi nào dùng cầu này thay DDS-Router

- **Máy chưa build DDS-Router.** `domain_bridge` cài bằng apt trong vài giây,
  DDS-Router phải build từ nguồn ~4 phút (không có gói apt).
- **Hợp đồng cần lại một ROS 2 service.** `domain_bridge` là ROS-native nên
  bắc cầu được cả service; DDS-Router 2.2.0 **không** — request qua được
  nhưng reply không bao giờ về (đo kỹ, xem `docs/TEST_PLAN_RESULTS.md` → M4).
  Hiện cả 3 giao diện đều là topic nên điểm này chưa dùng tới.

Đây cũng chính là lý do `b2/drone_cmd` là topic chứ không phải service
`b2/cmd` như trước: bỏ service khỏi đường M4 để **cả hai** cầu đều chạy được.
`box_state_manager` vẫn phục vụ service `b2/cmd` cho vai trò operator/server —
vai trò đó không đi qua ranh giới domain.

## Chạy

```bash
# Một lần
sudo apt install -y ros-humble-domain-bridge
cd ros2_ws && colcon build --packages-select dib_domain_bridge

# Terminal cầu (KHÔNG export ROS_DOMAIN_ID — cầu tự nối hai domain)
ros2 run dib_domain_bridge dib_split_bridge 42 0    # arg1=box domain, arg2=drone domain
```

Run-sheet đầy đủ (7 terminal, box `ROS_DOMAIN_ID=42` / drone `=0`, cùng
`dib_bringup.launch.py include_telemetry_bridge:=false`):
`docs/m4_split_domain_test/README.md`.
