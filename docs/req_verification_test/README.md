# Kiểm chứng yêu cầu bậc cao (REQ_*) trong SITL — GUIDE ĐẦY ĐỦ

Chạy **2 lượt**: Lượt A (loop bình thường) chốt 5 mục; Lượt B (một tham số) chốt
fallback. Làm đúng thứ tự, không bỏ bước. Mọi terminal ROS dùng chung header dưới.

## 0. Build một lần (nếu chưa)
```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
colcon build
```

## Header dán vào MỌI terminal ROS (trừ T1 phần make)
```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
```
Single-domain (KHÔNG export ROS_DOMAIN_ID). Mọi lệnh dùng đường dẫn tuyệt đối
nên chạy từ thư mục nào cũng được.

---

# LƯỢT A — loop bình thường (TALA_0007, TALA_0008, FEA_0003, PHY_0005/0006, regression)

## Terminals
| T | Lệnh |
|---|---|
| 1 | `export GZ_SIM_RESOURCE_PATH=$HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share`<br>`cd ~/PX4 && PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing` |
| 2 | `ros2 launch box_simulation box_spawn_only.launch.py` |
| 3 | `ros2 launch precision_landing sitl_precland.launch.py 2>&1 \| tee /tmp/precland.log` |
| 4 | `ros2 launch precision_landing sitl_mavros.launch.py` |
| 5 | `ros2 launch precision_landing dib_bringup.launch.py` |
| 6 | `ros2 launch ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/sitl_fixtures.launch.py` |
| 7 | `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/measure_actuator_timing.py` |
| 8 | `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/m3_full_loop_monitor.py` |

Bật T1→T6 (đợi mỗi cái ổn định), rồi T7 + T8 TRƯỚC khi bay. Bay bài như M3.

## Trong lúc/ sau khi bay — thu 5 kết quả

### (A1) REQ_BOX_FEA_0003 — telemetry đủ  → làm NGAY khi hệ thống chạy (chưa cần bay)
Terminal mới (header):
```bash
ros2 topic echo --once /b2/telemetry
```
**ĐẠT nếu:** `box_environment` KHÁC 0 (wind/temp/hum…), `box_info.latitude/longitude`
KHÁC 0, và có các field: `status_door, status_hold, is_empty, connected,
air_conditioner, status_power`.

### (A2) REQ_UAV_TALA_0008 (vị trí <15cm) + (A3) REQ_UAV_TALA_0007 (góc <10°)
Sau khi drone chạm đất, xem T3 (hoặc `grep TOUCHDOWN /tmp/precland.log`):
```
TOUCHDOWN: drone=(...)  aim=(...)  aim_error=0.016m  ...
TOUCHDOWN yaw: drone=88.1deg  marker=88.1deg  yaw_error=0.00deg  (REQ_UAV_TALA_0007 threshold 10deg)
```
**ĐẠT nếu:** `aim_error < 0.15 m` (TALA_0008) và `yaw_error < 10 deg` (TALA_0007).

### (A4) REQ_BOX_PHY_0005/0006 — thời gian cửa/kẹp  → xem T7
T7 in ví dụ:
```
[LID] OPEN took 2.91s / [LID] CLOSE took 3.28s
[CLAMP-H] CLOSE ...->200mm took 2.67s / [CLAMP-V] CLOSE ...->200mm took 2.88s
```
**Kết quả = số đo** (đặc tả trống ngưỡng → chỉ ghi số, không ĐẠT/FAIL). Ctrl-C T7 khi xong.

### (A5) Regression — không hồi quy  → xem T8 (hoặc T5)
**ĐẠT nếu:** T8 (`m3_full_loop_monitor.py`) báo **8/8**, và T5/box đạt
`Box in CHARGING state`; T3 in `Box reached CHARGING — cycle complete`.

Tắt hết (Ctrl-C mỗi terminal) trước Lượt B.

---

# LƯỢT B — fallback (REQ_UAV_FLY_0020, mã lỗi 0002)

Giống Lượt A NHƯNG **T3 đổi thành** (thêm `require_rtk:=true`):
```bash
ros2 launch precision_landing sitl_precland.launch.py require_rtk:=true 2>&1 | tee /tmp/precland_fb.log
```
Các terminal khác (T1,T2,T4,T5,T6) y hệt Lượt A. (T7/T8 không cần.)

Bay như thường. Vì thiếu RTK, drone sẽ **KHÔNG bắt tay box** mà rơi vào FALLBACK
ngay ở PRELANDING_CHECK và tự hạ cánh dự phòng.

### (B1) REQ_UAV_FLY_0020 — kiểm mã 0002
T3 phải in:
```
PRELANDING_CHECK: require_rtk set but no RTK fix -- unsafe. FALLBACK.
```
Rồi ở terminal mới (header), khi drone đang/đã FALLBACK:
```bash
ros2 topic echo --once /d1/telemetry
```
**ĐẠT nếu:** `error: [2]` (mã 0002) xuất hiện trong DroneTelemetry.
(Ở Lượt A bình thường `error:` rỗng `[]` — đó là đối chứng.)

> Ghi chú: bất kỳ FALLBACK nào (mất marker, box không sẵn sàng, timeout…) đều phát
> mã 0002 như nhau; require_rtk:=true chỉ là cách kích FALLBACK tất định để test.

---

# Bảng thu kết quả (điền vào rồi gửi lại)

| REQ | Cách đọc | Ngưỡng | Kết quả của bạn |
|---|---|---|---|
| REQ_UAV_TALA_0008 | TOUCHDOWN `aim_error` | < 0.15 m | ____ m |
| REQ_UAV_TALA_0007 | TOUCHDOWN `yaw_error` | < 10° | ____° |
| REQ_BOX_FEA_0003 | echo /b2/telemetry | env≠0 + field mới | ĐẠT / CHƯA |
| REQ_BOX_PHY_0005 | T7 [LID] | (chỉ đo) | mở __s / đóng __s |
| REQ_BOX_PHY_0006 | T7 [CLAMP] | (chỉ đo) | H __s / V __s |
| REQ_UAV_FLY_0020 | echo /d1/telemetry (Lượt B) | error:[2] | ĐẠT / CHƯA |
| Regression | monitor 8/8 + CHARGING | 8/8 | ____/8 |

Kết quả tham chiếu (bay 2026-08-03): TALA_0008=0.016m ✅, TALA_0007=0.00° ✅,
FEA_0003 ✅, PHY cửa 2.91/3.28s, kẹp H2.67/V2.88s, regression tới CHARGING ✅.
