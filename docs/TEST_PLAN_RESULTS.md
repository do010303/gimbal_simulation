# Test Plan & Kết Quả — Drone-in-a-Box

File này gom quy trình test và kết quả cho từng milestone trong
`docs/Drone_In_A_Box_Design_Milestones.docx`. Mỗi milestone có 1 mục
riêng: mục tiêu, điều kiện tiên quyết, quy trình chạy, tiêu chí pass/fail,
và log kết quả các lần chạy (mới nhất lên đầu).

## Tổng quan tiến độ

| Milestone | Nội dung | Trạng thái | Lần test gần nhất |
|---|---|---|---|
| M1 | Build & chạy độc lập `box_manager` | ✅ PASS | 2026-07-20 |
| M2 | Box hardware adapter + MAVROS→dib_msgs telemetry bridge | ✅ PASS (6a box-side + 6b MAVROS đều PASS) | 2026-07-22 |
| M3 | Vòng khép kín drone↔box trên world hợp nhất — bắt tay (M3a) · marker trên thân box (M3b) · vòng đời→`CHARGING` (M3c) · dọn log + báo vị trí (M3d) | ✅ **PASS 8/8** — **sai số hạ cánh thật 4.9 cm** | 2026-07-29 |
| M4 | Tách domain box↔drone + bắc cầu hợp đồng (**DDS-Router 2.2.0**; `domain_bridge` = dự phòng) | ✅ **PASS 8/8 ĐẦY ĐỦ** — tầng-2 Gazebo vòng kín tới `CHARGING` với driver tự động chấm 8/8 (không đọc log tay); cộng nhân quả "tắt cầu giữa chừng một chuyến bay thật" (box kẹt `EMPTY` 39.5s, `FALLBACK` tự kích hoạt đúng 30s, `aim_error` rơi từ 2.2cm xuống 2.385m khi mất cầu). Chứng minh bằng socket: router giữ cả cổng 7400 (domain 0) lẫn 17900 (domain 42), node ROS mỗi bên chỉ giữ một | 2026-08-05 |
| M5 | Hardening + đóng gói | ⬜ Chưa bắt đầu | — |

---

## M1 — Build & chạy độc lập `box_manager`

### Mục tiêu
Xác nhận `box_manager` build sạch khi trỏ vào `dib_msgs` local (qua
symlink chung workspace `SITL_PrecisionLanding/ros2_ws`), và
`box_state_manager_node` chạy đúng toàn bộ state machine landing:

```
EMPTY -> IDLE -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING -> SECURING_DRONE -> CHARGING
```

bao gồm cả 2 sub-FSM lồng bên trong (`PreparingStateManager`,
`SecuringStateManager`).

### Điều kiện tiên quyết
- `examples/SITL_PrecisionLanding/ros2_ws/src/box_manager` và
  `.../box_simulation` đã symlink vào workspace chính.
- ROS 2 Humble đã cài, `colcon build --packages-up-to box_manager` chạy
  sạch trong `ros2_ws`.

### Thành phần test

Vì M2 (hardware adapter thật nối `box_simulation` Gazebo) chưa làm, M1
dùng 1 stub tạm để đóng vai "phần cứng box" — **không phải deliverable
M2**, chỉ để cô lập và test đúng state machine logic của `box_manager`:

| File | Vai trò |
|---|---|
| `~/m1_box_manager_test/mock_hw_stub.py` | Serve `/lid/cmd`, `/clamp/cmd`, `/dock/{power_button,charge,cooling_battery}/cmd`, luôn trả `success=true` ngay lập tức, publish lại `/lid/status`, `/clamp/status` phản ánh lệnh vừa nhận |
| `~/m1_box_manager_test/m1_state_test.py` | Driver: gọi `BoxCmd(REQUEST_LANDING)` qua `/b2/cmd`, publish 1 lần `DroneTelemetry(ON_GROUND)` lên `/d1/telemetry` khi thấy `WAITING_FOR_LANDING`, theo dõi `/box/state` tới `CHARGING`, in bảng trace + `PASS`/`FAIL` |

> Stub không mô phỏng độ trễ cơ khí hay lỗi phần cứng — chỉ chứng minh
> đúng **state machine logic**, chưa chứng minh gì về tích hợp với
> `box_simulation` Gazebo thật (đó là nội dung M2).

### Quy trình chạy

**Terminal 1 — box_manager:**
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
ros2 run box_manager box_state_manager_node \
  --ros-args --params-file src/box_manager/config/box_state_manager.yaml
```
Kỳ vọng: log `Box in EMPTY state` lặp lại 10Hz, chưa có gì tác động.

**Terminal 2 — mock hardware stub:**
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
python3 ~/m1_box_manager_test/mock_hw_stub.py
```

**Terminal 3 — driver test:**
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
python3 ~/m1_box_manager_test/m1_state_test.py
```
Script tự thoát khi đạt `CHARGING` hoặc sau 25s timeout; in bảng trace
và `RESULT: PASS`/`FAIL` (exit code 0/2).

**Terminal 4 (tuỳ chọn) — theo dõi trực tiếp:**
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic echo /box/state
```

Muốn chạy lại từ đầu: Ctrl+C Terminal 1 và 2 rồi mở lại (state chỉ
reset khi node khởi động lại, không có persistence).

### Tiêu chí Pass
- `colcon build --packages-up-to box_manager` không lỗi, không cần sửa
  code (`package.xml`/`CMakeLists.txt` chỉ khai `dib_msgs` theo tên).
- `/box/state` đi đúng thứ tự đủ 6 state:
  `EMPTY(0) -> IDLE(1) -> PREPARING_FOR_LANDING(6) -> WAITING_FOR_LANDING(7) -> SECURING_DRONE(8) -> CHARGING(9)`.
- Không có state nào bị bỏ qua hoặc lặp vòng lỗi (`ERROR(101)`).
- Topic/service khớp README: `/b<box_id>/telemetry`, `/box/state`,
  `/b<box_id>/cmd`, `/box/mission_upload`, và 5 client service
  lid/clamp/power/charge/cooling.

### Tiêu chí Fail
- Build lỗi hoặc phải sửa code `box_manager` mới build được.
- State machine kẹt ở bất kỳ state nào quá thời gian timeout riêng của
  nó (`WAITING_TIMEOUT=90s`, `LANDING_TIMEOUT=120s`,
  `CLAMP_H_CLOSE_TIMEOUT=30s`, `TIME_OUT=60s` cho securing).
- Rơi vào `BoxState::ERROR`.

### Kết quả lần chạy gần nhất

```
Ngày:        2026-07-20
Kết quả:     PASS
box_id:      2   |  drone_id (agent_id/10): 1
```

| t (s) | State |
|---|---|
| 0.00 | EMPTY (0) |
| 0.20 | IDLE (1) |
| 0.40 | PREPARING_FOR_LANDING (6) |
| 0.60 | WAITING_FOR_LANDING (7) |
| 0.80 | SECURING_DRONE (8) |
| 7.30 | CHARGING (9) |

Ghi chú: khoảng dừng ~6.5s giữa `SECURING_DRONE` và `CHARGING` là
**đúng thiết kế**, không phải lỗi — `WAITING_DRONE_REQUEST_POWER_OFF`
trong `securing_state_manager.cpp` chờ telemetry drone "nguội" quá 5s
mới tự chuyển `DONE -> CHARGING`.

Log service call xác nhận:
```
BoxCmd REQUEST_LANDING response success=True
published /d1/telemetry landed_state=ON_GROUND
```

### Việc còn lại trước khi đóng hẳn M1
- [ ] Test thêm nhánh lỗi (weather fail, timeout, service unavailable) để
      xác nhận `checkNewState` rơi đúng vào `ERROR` với `BoxStateError`
      tương ứng.
- [ ] Quyết định có đưa `mock_hw_stub.py`/`m1_state_test.py` vào repo
      làm test chính thức (`examples/box_manager/test/`) hay giữ ở ngoài.

---

## M2 — Box hardware adapter + MAVROS→dib_msgs telemetry bridge

### Mục tiêu
Thay 2 stub của M1 bằng 2 node C++ cầu nối thật:
- `box_hardware_adapter_node` (package `box_hardware_adapter`) — dịch dib_msgs
  service/status ↔ ros2_control JointTrajectory của `box_simulation`.
- `mavros_to_dib_telemetry` (thêm vào package `precision_landing`) — dịch
  `/mavros/{state,extended_state}` → `d<drone_id>/telemetry`.

### Trạng thái build (2026-07-22)
- [x] `colcon build --packages-select box_hardware_adapter precision_landing box_manager` — sạch, 13.2s.
- [x] 2 executable install đúng: `box_hardware_adapter_node`, `mavros_to_dib_telemetry`.
- [x] Kiểm tra ROS graph khi chạy: adapter serve đủ 5 service
  (`/lid/cmd`, `/clamp/cmd`, `/dock/{power_button,charge,cooling_battery}/cmd`),
  publish đủ status (`/lid/status`, `/clamp/status`, `/dock/charge/status`,
  `/dock/cooling_battery/status`), publish tới 3 topic JTC; bridge publish
  `/d1/telemetry`, subscribe `/mavros/state` + `/mavros/extended_state`.

### 6a-unit — Adapter logic (không cần Gazebo controller) ✅ PASS (2026-07-22)
Driver: `docs/m2_box_manager_test/m2_adapter_unit_test.py`. Bơm `/joint_states`
giả + gọi service, kiểm chứng cả 2 đường dữ liệu của adapter độc lập với Gazebo:

```
/lid/cmd(open)  -> lid traj target 1.57 rad         : PASS (got [1.57])
/clamp/cmd      -> clamp_h/clamp_v traj 0.2 m        : PASS
/joint_states   -> /lid/status CLOSED->OPENING->OPENED : PASS
/joint_states   -> /clamp/status đạt 200 mm          : PASS (max=200 mm)
OVERALL: PASS
```
→ Chứng minh code adapter M2 đúng (dịch service→JointTrajectory và
JointState→status), kể cả unit-mapping mm và suy luận OPENING/CLOSING.

### 6a-full — Lid/clamp di chuyển thật trên Gazebo ✅ PASS (2026-07-22)
Driver: `docs/m2_box_manager_test/m2_full_stack_test.py`.

**Blocker đã được giải quyết.** Ban đầu bị chặn: Gazebo trên máy là **Harmonic
(gz-sim8)** (bản PX4 dùng) nhưng gói apt `ros-humble-gz-ros2-control` build cho
**Fortress** → thiếu `GzPluginHook` → plugin ros2_control không load, không có
`controller_manager`/`/joint_states`.

**Fix (2026-07-22):** build `gz_ros2_control` từ source cho Harmonic:
```bash
mkdir -p ~/gz_ros2_control_ws/src && cd ~/gz_ros2_control_ws/src
git clone -b humble --depth 1 https://github.com/ros-controls/gz_ros2_control.git
cd ~/gz_ros2_control_ws
export GZ_VERSION=harmonic
colcon build --packages-select gz_ros2_control --cmake-args -DCMAKE_BUILD_TYPE=Release
```
Thư viện mới `~/gz_ros2_control_ws/install/gz_ros2_control/lib/libgz_ros2_control-system.so`
có symbol `GzPluginHook` (verify: `nm -D ... | grep GzPluginHook`), env hook tự
prepend vào `GZ_SIM_SYSTEM_PLUGIN_PATH`. **Đã xác nhận** plugin load thành công,
`controller_manager` lên, cả 4 controller active:
```
[gz_ros2_control]: System Successfully configured!
Successfully loaded controller joint_state_broadcaster into state active
Successfully loaded controller joint_clamp_v_controller into state active
Successfully loaded controller joint_lid_controller into state active
Successfully loaded controller joint_clamp_h_controller into state active
```

**Cách chạy 6a** (thêm 1 dòng source overlay so với hướng dẫn cũ):
```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash          # <-- BẮT BUỘC: plugin Harmonic đã fix
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch box_hardware_adapter box_full_stack.launch.py
# terminal 2:
python3 docs/m2_box_manager_test/m2_full_stack_test.py
```

Tiêu chí Pass:
- `/joint_states.lid_left_joint` di chuyển >0.5 rad.
- `/lid/status` có `OPENING`/`CLOSING`.
- `/clamp/status.clamp_h_pos` đạt ~200 mm và `box_info.clamp_state` = CLOSED.

Kết quả: ✅ **PASS (2026-07-22, chạy interactive trên Gazebo thật)**

```
=== M2 6a STATE TRACE ===
  t+ 0.00s  EMPTY (0)
  t+ 0.20s  IDLE (1)
  t+ 0.40s  PREPARING_FOR_LANDING (6)
  t+ 2.61s  WAITING_FOR_LANDING (7)
  t+ 2.80s  SECURING_DRONE (8)
  t+11.80s  CHARGING (9)

lid_left_joint range (rad):     ~0 .. 1.570   (delta=1.570)  -> lid mở thật
/lid/status values seen:        CLOSED, CLOSING, OPENED, OPENING
/clamp/status.clamp_h_pos (mm): 0 .. 200
box_info.clamp_state = CLOSED:  True

state sequence EMPTY..CHARGING : PASS
lid actually moved (>0.5 rad)  : PASS
lid OPENING/CLOSING observed   : PASS
clamp reached ~200 mm          : PASS
OVERALL                        : PASS
```

> **Chạy lại phải restart launch:** sau 1 chu kỳ box đã ở CHARGING và FSM từ chối
> `REQUEST_LANDING` mới (`box_state_manager.cpp` chỉ nhận REQUEST_LANDING khi
> EMPTY — đúng thiết kế, box đang giữ drone không nhận drone thứ 2). Muốn test
> lại từ đầu: Ctrl+C `box_full_stack.launch.py` rồi launch lại (reset về EMPTY).

> Ghi chú mimic: DART không hỗ trợ mimic constraint → nửa nắp/kẹp đối diện
> (`lid_right`, `clamp_h_2`, `clamp_v_2`) không tự nhân bản chuyển động. Adapter
> chỉ điều khiển/đọc joint chính (`lid_left`, `clamp_h_1`, `clamp_v_1`) nên
> status/logic vẫn đúng; chỉ hình ảnh Gazebo thấy 1 nửa cử động.

### 6b — MAVROS landed passthrough thật ✅ PASS (2026-07-22, PX4 SITL + MAVROS thật)
Driver: `docs/m2_box_manager_test/m2_telemetry_bridge_test.py`. 6 terminal
(PX4 SITL, MAVROS, box_state_manager, mock_hw_stub, mavros_to_dib_telemetry,
driver); bay bằng `commander takeoff`/`commander land` trong shell PX4.

DoD đạt — box tự chuyển qua tín hiệu landed THẬT, không publish tay:
```
box_state trace: EMPTY -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING -> SECURING_DRONE
box WAITING_FOR_LANDING -> SECURING_DRONE happened      : PASS
landed_state at that transition was ON_GROUND           : PASS
(no DroneTelemetry hand-published by the driver)
```
Chuỗi: drone cất cánh (IN_AIR) → box tới WAITING khi đang bay → `commander land`
→ box tự sang SECURING_DRONE ngay khi PX4 land detector báo chạm đất, qua bridge.

**Ghi chú thước đo (đã sửa driver):** lần chạy đầu báo `bridge fidelity FAIL`
(29/536 mismatch) — KHÔNG phải lỗi bridge, mà do thước đo cũ so 2 luồng async
tức thời nên đếm cả độ trễ 1-message lúc chuyển trạng thái (bridge event-driven,
d1 phản ánh giá trị mới ở message kế tiếp, <~100ms). Đã sửa metric: chỉ tính lỗi
nếu d1 không đuổi kịp sau grace 0.4s (`fidelity_persistent_mismatches`). Với
metric mới, 29 mismatch đều là transient lag → PASS. DoD thực chất luôn đạt ngay
từ lần chạy đầu.

### Known gap (không chặn M2)
- Cảm biến GPS trong `box.xacro` là `type="navsat"` (Ignition/gz-sim8; `type="gps"`
  của Classic Gazebo không tồn tại trên máy này), nhưng **chưa có `ros_gz_bridge`**
  nào biến `navsat` thành topic ROS2 `sensor_msgs/NavSatFix` (`gps`) mà box_manager
  cần. Hệ quả: `box_info.latitude/longitude` = 0 trong SITL. Không ảnh hưởng luồng
  landing (M1 đã chứng minh FSM chạy đúng không cần GPS). Thuộc phạm vi refactor
  `box_simulation`, không phải M2.

### Tổng kết M2 — ✅ HOÀN THÀNH (3/3 test PASS trên hệ thống thật)

Deliverables (code):
- **`examples/box_hardware_adapter/`** (package C++ mới) — adapter dib_msgs ↔
  ros2_control, symlink vào `ros2_ws/src/`.
- **`precision_landing/.../mavros_to_dib_telemetry_node.{hpp,cpp,_main.cpp}`** +
  CMakeLists (component thứ 4) — bridge MAVROS → dib_msgs.
- `box_state_manager.yaml`: `pos_clamp_h/v_close` 8850/4100 → 200 (giữ comment giá
  trị phần cứng gốc).
- `box.launch.py` / `add_box.launch.py`: bỏ node phantom `box_management`.
- `box.xacro`: tên plugin `ign_ros2_control` → `gz_ros2_control` (tương thích Harmonic).

Điều kiện môi trường (fix hạ tầng, làm 1 lần):
- Build `gz_ros2_control` cho Harmonic tại `~/gz_ros2_control_ws` (xem 6a-full).
  **Phải `source ~/gz_ros2_control_ws/install/setup.bash`** trước khi launch bất
  kỳ thứ gì dùng `box_simulation` controllers.

Test drivers (trong `docs/m2_box_manager_test/`, gitignored):
- `m2_adapter_unit_test.py` (6a-unit), `m2_full_stack_test.py` (6a-full),
  `m2_telemetry_bridge_test.py` (6b).

Cần nhắc chủ nhánh `feature/hung_refactor_urdf` (hung): 2 fix trong `box.xacro`
plugin name + build `gz_ros2_control` cho Harmonic là bắt buộc để `box_simulation`
có controller trên máy PX4; nên đưa vào tài liệu setup của nhánh refactor.

---

## M3 — Vòng khép kín drone↔box trên world hợp nhất

> **Gộp M3 + M3.5 + M3.6 (2026-07-29).** Ba mốc này là **một câu chuyện**: bắt
> tay để box mở cửa (M3a), gắn marker lên thân box và hạ trong cùng một world
> (M3b), khép vòng đời tới `CHARGING` (M3c), cộng đợt dọn log + hiệu chỉnh báo
> vị trí để hệ thống *đo được* (M3d). Kết luận và số liệu chuẩn nằm ngay dưới;
> chi tiết từng giai đoạn + nhật ký bẫy giữ nguyên trong các mục con. Kế hoạch
> đầy đủ của giai đoạn hợp nhất world: `M3_5_PLAN.md` (phụ lục).

### Kết luận & số liệu chính xác (2026-07-29)

Vòng drone-in-a-box chạy **end-to-end trong MỘT world Gazebo duy nhất**, không
thao tác tay, không driver bơm lệnh:

```
drone bay tới box (GPS) → tự gửi REQUEST_LANDING → box mở nắp/kẹp THẬT (Gazebo)
→ box WAITING_FOR_LANDING(7) → drone hạ cánh thị giác lên marker trên thân box
→ chạm đất & disarm → box kẹp ngang/dọc + đóng nắp → drone gửi TURN_OFF_DRONE
→ box CHARGING(9).   Monitor thụ động: PASS 8/8.
```

**Số liệu đo được — đã kiểm, không phải cảm tính:**

| Đại lượng | Giá trị | Cách lấy |
|---|---|---|
| **Sai số hạ cánh THẬT** | **4.9 cm** | `TOUCHDOWN drone=(2.4874,−2.5473)` − marker `(2.5129,−2.5896)` |
| Sai số bám của vòng điều khiển | 2.0 cm | `aim_error` = drone − điểm ngắm tracker (cùng dòng `TOUCHDOWN`) |
| Hình học dọc ở tầm flare | khớp 0.519 m trong ±2 cm | `measure_altitude_datum.py`: gap_v = 0.51–0.54 dưới 3.5 m |
| Lệch gốc z (datum) gần đất | ≈ 0 | gap_v gần đất ≈ dự đoán → EKF origin nằm ở mặt đất |
| `marker_size` = 0.50 m | ĐÚNG | đo trực tiếp `marker.png`: đen 959/1197 = 0.8012 × plane 0.6241 = 0.500 m; tầng L1/L2 khớp `custom_fractal.yml` tới từng pixel |
| Độ trễ tracker | 4–8 ms xử lý · 44–52 ms nguồn→tracker | dưới ngưỡng 100 ms suốt quá trình |
| Độ ồn log `dib_bringup` | 77 dòng / cả chuyến · **0 dòng lặp theo tick** | `wc -l`; mỗi `Box in <STATE>` đúng 1 lần |

**Đính chính các con số cũ (quan trọng — vì tài liệu cũ có ghi sai):**
- Mọi "sai số hạ cánh 3–4 cm" ghi TRƯỚC 2026-07-23 thực ra là **sai số ước lượng
  marker của tracker** (`final_xy` = điểm ngắm), **không phải** vị trí drone. Sai
  số hạ cánh THẬT lần đầu đo được là **4.9 cm** (dòng `TOUCHDOWN`, M3c).
- Phỏng đoán "lệch datum 0.18 m" là **sai** — số đo 2026-07-29 cho thấy datum ≈ 0
  ở tầm flare.
- Chênh `U` vs `MARKER DIST` trên HUD là **đúng** (0.519 m = cao độ marker −
  cao độ camera), không phải lỗi đồng bộ, cũng không phải sai `marker_size`.

**Còn treo (không chặn M3 — chuyển tiếp):**
- **Phép thử scale ngang (B) chưa kết luận.** Lần đo drone hạ gần thẳng đứng
  (lệch ngang tối đa 0.36 m) nên phép B thiếu đòn bẩy. Muốn chốt scale độc lập
  cần một lượt **tiến ngang tới box từ 4–5 m** trước khi hạ. Dữ liệu dọc gần đất
  đã cho thấy scale ổn ở vùng flare, nên không phải blocker.
- `camera_offset_x` (config `0.157` vs model `0.126`) — **vào setpoint ngang**,
  đổi là đổi hành vi đang chạy tốt; đo riêng, để M5.
- `box_manager` (repo GitLab của team khác) có 2 commit local dọn log
  (`50e5a12`, `a62fe49`) — chưa quyết định push hay gửi patch.

---

### M3a — Bắt tay FSM (BoxLink + 2 state mới trong offboard_precland_controller)

#### Mục tiêu

Khép kín vòng drone↔box: drone **tự** yêu cầu box mở nắp/kẹp, chờ box báo sẵn
sàng, rồi mới bắt đầu hạ cánh thị giác. Trước M3, `offboard_precland_controller`
bay tới box bằng GPS rồi vào `START` luôn — box không bao giờ được báo là có
drone đang về.

#### Thay đổi code (2026-07-22)

**Mới:**
- `precision_landing/include/precision_landing/box_link.hpp`
- `precision_landing/src/box_link.cpp`

`BoxLink` giữ client `dib_msgs/srv/BoxCmd` tới `b<box_id>/cmd`.
`request_landing()` gửi `BoxCmd{command=REQUEST_LANDING(23),
agent_id=drone_id*10+2}`, **bất đồng bộ** (`async_send_request` + callback,
không bao giờ `wait_for_service()` blocking) — gọi blocking trong control loop
sẽ làm nghẽn luồng setpoint và PX4 rớt OFFBOARD.

> **Quyết định thiết kế:** `BoxLink` **không** tự subscribe `/b<box_id>/telemetry`.
> Controller đã có sẵn `sub_box_telemetry_` (nuôi `box_lat_/box_lon_/box_yaw_`
> cho `GOTO_BOX`, đã bay thật). `on_box_telemetry()` đẩy `box_state` sang
> `BoxLink` qua `set_box_state()`. Một subscription nuôi cả hai → không thể có
> chuyện hai bên hiểu khác nhau về "box nào".

**Sửa `offboard_precland_controller.{hpp,cpp}`:**

| Chỗ sửa | Nội dung |
|---|---|
| `enum PrecLandState` | thêm `PRELANDING_CHECK`, `WAIT_BOX_READY` |
| `can_transition()` | thêm 3 cạnh: `GOTO_BOX→PRELANDING_CHECK`, `PRELANDING_CHECK→WAIT_BOX_READY`, `WAIT_BOX_READY→START` |
| `st_goto_box()` | nhánh **tới nơi** đổi `→START` thành `→PRELANDING_CHECK`; nhánh **timeout telemetry** giữ nguyên `→START` |
| `st_prelanding_check()`, `st_wait_box_ready()` | 2 handler mới + 2 case dispatch + 2 case tên state (2 chỗ) |
| `init_visual_landing()` | helper mới, gom khối reset tracker vốn bị lặp 2 lần |
| Params | `box_id`, `drone_id`, `prelanding_timeout_sec`, `box_ready_timeout_sec` |

#### Nguồn gốc code — không có Python local nào được nhúng vào C++

Kiểm bằng git (2026-07-22):

| File | Nguồn |
|---|---|
| `box_link.{hpp,cpp}` | **100% mới**, viết trong session này (untracked) |
| `offboard_precland_controller.{hpp,cpp}` sửa đổi | mới, trên nền file có sẵn của `origin/main` |
| `mavros_to_dib_telemetry_node.*` (M2) | **100% mới** (untracked) |

`origin/main` (TeedeeTD) **không** có `BoxCmd`, `REQUEST_LANDING`, `box_state`,
`PRELANDING_CHECK` hay `WAIT_BOX_READY` trong `offboard_precland_controller.cpp`
→ toàn bộ phần bắt tay C++ là code mới.

#### Trạng thái build (2026-07-22)

```
colcon build --packages-select precision_landing --cmake-args -DCMAKE_BUILD_TYPE=Release
Finished <<< precision_landing [29.3s]   # sạch, không warning
```
Smoke test khởi động node:
```
[INFO] [offboard_precland_controller]: BoxLink: box_id=1 drone_id=1, cmd service 'b1/cmd', agent_id=12
```
→ tên service và `agent_id` khớp đúng `box_state_manager.cpp`.

#### 7a — Handshake FSM unit test ✅ PASS (2026-07-22)

Mock cả MAVROS lẫn box, **không cần PX4/Gazebo/MAVROS thật** — cùng triết lý
với 6a-unit của M2: tách logic mới khỏi hạ tầng nặng để lỗi (nếu có) chỉ trỏ
vào code.

Quy trình: xem `m3_box_handshake_test/README.md` (2 terminal).

Kết quả chạy:
```
--- FSM trace ---
IDLE -> FLIGHT_IN_PROGRESS -> GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START

--- BoxCmd requests seen by the mock box ---
  command=23 agent_id=12 (box_state=0)

--- criteria ---
  [PASS] FSM passes GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY -> START
         all four states in order
  [PASS] REQUEST_LANDING sent with agent_id == 12
         1 request(s), agent_ids=[12]
  [PASS] REQUEST_LANDING accepted exactly once (idempotent, no spam)
         1 accepted, 1 total sent
  [PASS] Left WAIT_BOX_READY only after box reported WAITING_FOR_LANDING(7)
         held station 5.1s (box prepared for 5.0s)

=== M3 unit test: PASS ===
```

Ý nghĩa từng tiêu chí:
- **#1** bắt lỗi thiếu cạnh whitelist (cạm bẫy 1 ở trên).
- **#2** chứng minh encoding `agent_id = drone_id*10 + 2` đúng với nhánh
  `agent_id % 10 == 2` của `box_state_manager.cpp`.
- **#3** `request_landing()` được gọi **mỗi tick** trong 5 giây mà box chỉ nhận
  đúng **1** request → guard idempotent hoạt động, không spam box.
- **#4** drone giữ vị trí 5.1s, chỉ rời `WAIT_BOX_READY` sau khi box báo state 7
  → không chạy trước nắp/kẹp box.

#### 7b — Full closed loop (PX4 SITL thật) ✅ PASS (lần 2, 2026-07-22)

##### 2 blocker đã phát hiện & sửa TRƯỚC khi chạy

**B1. `box_id` lệch nhau → bắt tay không bao giờ xảy ra.**
`box_state_manager.yaml` đặt `box_id: 2` (box phục vụ `b2/cmd`, publish
`b2/telemetry`), nhưng `offboard_precland_params.yaml` mặc định `box_id: 1`.
Drone sẽ gọi `b1/cmd` (không tồn tại) và chờ `/b1/telemetry` (không có ai
publish) → `box_telemetry_valid_` mãi false → `st_flight_in_progress()` đi
thẳng sang `START`, **bỏ qua toàn bộ M3**, mà không có lỗi nào.
*Sửa:* `box_id: 2` trong `offboard_precland_params.yaml`. Logic derive tự đổi
`box_telemetry_topic` → `/b2/telemetry`. Đã verify bằng log khởi động:
```
Derived box_telemetry_topic='/b2/telemetry' from box_id=2
BoxLink: box_id=2 drone_id=1, cmd service 'b2/cmd', agent_id=12
```

**B2. `box_info.latitude/longitude = 0` → drone bay ra giữa đại dương.**
`box_state_manager` lấy toạ độ box từ topic `gps` (`sensor_msgs/NavSatFix`,
xem `box_state_manager.cpp:68,187-194`). Trong SITL **không ai publish topic
này** (sensor `navsat` của box_simulation chưa có `ros_gz_bridge` — known gap
đã ghi ở M2). Hậu quả: `st_goto_box()` tính
`dlat = 0.0 − 47.398 = −47.4°` → setpoint cách hàng nghìn km. Đây là blocker
cứng, không phải lỗi thẩm mỹ.
*Sửa:* thêm fixture `m3_box_handshake_test/box_gps_publisher.py`, publish `/gps`
tại đúng vị trí pad, toạ độ **suy ra từ world** chứ không đoán:
```
fractal_aruco_landing.sdf: origin lat 47.397971057728974 lon 8.546163739800146
dib_box_landing_pad pose = 4.0 -3.5 0  (ENU: East, North)
=> pad lat 47.397939617, lon 8.546216824
```
*Không sửa `mock_hw_stub.py` của M1* để test M1 vẫn tái lập được y nguyên.

> Còn lại ~1.9 m sai số do `box_state_manager` cộng thêm antenna offset
> (`y_anten_gps_offset: 1.9`). Nằm gọn trong `goto_box_arrival_radius: 3.0` và
> sau đó hạ cánh thị giác tiếp quản → vô hại. Đừng "sửa" bằng cách bịa lại toạ
> độ; nếu cần chính xác thì đổi offset trong `box_state_manager.yaml`.

##### Vì sao KHÔNG dùng box Gazebo trong 7b

Ban đầu tôi định chạy `box_full_stack.launch.py` (box Gazebo thật) song song
PX4 SITL. Bỏ, vì:
- Đó là **2 tiến trình Gazebo riêng biệt, 2 world riêng biệt**. Drone không thể
  nhìn thấy nắp/kẹp của world kia — marker mà camera drone thấy nằm trong world
  của PX4 (`dib_box_landing_pad`), không phải trong world box_simulation.
- Cơ cấu nắp/kẹp thật **đã được chứng minh ở 6a** rồi.
- `docs/BOX_HYBRID_SITL_PLAN.md` (bản plan gốc của team, trong git history) cũng
  chỉ định runtime shape dùng `mock_box_hardware_node`, không dùng box Gazebo.

Nên 7b = **PX4 + hạ cánh thật + bắt tay thật + FSM box thật**, cơ cấu chấp hành
của box dùng mock. Hợp nhất 2 world là việc riêng, để M5 hoặc chấp nhận là giới
hạn của SITL.

##### Quy trình — 6 terminal

Mỗi terminal đều cần:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

| T | Lệnh | Vai trò |
|---|---|---|
| T1 | `cd ~/PX4 && make px4_sitl gz_x500_gimbal_fractal_aruco_landing` | PX4 + Gazebo world. Giữ `pxh>` để bay |

> **Camera Gazebo bị khoá theo drone → dùng `PX4_GZ_NO_FOLLOW=1`:**
> ```bash
> cd ~/PX4 && PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing
> ```
> Nguồn: `ROMFS/px4fmu_common/init.d-posix/px4-rc.gzsim:162`
> ```sh
> if [ -z "${PX4_GZ_NO_FOLLOW}" ]; then
>     gz topic -t /gui/track -m gz.msgs.CameraTrack \
>         -p "track_mode: FOLLOW, follow_target: {name: '${MODEL_NAME_INSTANCE}'}, ..."
> fi
> ```
> Muốn giữ follow nhưng đổi góc nhìn: `PX4_GZ_FOLLOW_OFFSET_X/Y/Z`
> (mặc định `-2, -2, 2`).
>
> **Bỏ follow khi Gazebo ĐANG chạy** (không cần khởi động lại):
> ```bash
> gz topic -t /gui/track -m gz.msgs.CameraTrack -p "track_mode: NONE"
> ```
>
> ⚠️ `PX4_NO_FOLLOW` (thiếu `GZ`) **không tồn tại** — đừng dùng.
> `PX4_NO_FOLLOW_MODE` có thật nhưng chỉ dành cho gazebo-classic.
>
> Đọc toạ độ mà không cần GUI: `gz model --list`, `gz model -m Box -p`.
| T2 | `ros2 launch mavros px4.launch fcu_url:="udp://:14540@127.0.0.1:14557"` | MAVLink ↔ ROS 2 |
| T3 | `ros2 run box_manager box_state_manager_node --ros-args --params-file ~/PX4/examples/box_manager/config/box_state_manager.yaml` | FSM box thật |
| T4 | `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m1_box_manager_test/mock_hw_stub.py` **và** `python3 .../m3_box_handshake_test/box_gps_publisher.py` | cơ cấu box (mock) + GPS box (fixture B2) |
| T5 | `ros2 run precision_landing mavros_to_dib_telemetry --ros-args -p drone_id:=1` | cầu telemetry M2 (C++) |
| T6 | `ros2 launch precision_landing sitl_precland.launch.py` | gz bridges + tracker + **controller C++** |
| T7 | `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/m3_full_loop_monitor.py` | giám sát (thụ động) |

> ⚠️ `sitl_precland.launch.py` **đã bao gồm cả controller**. Đừng chạy thêm
> `ros2 run precision_landing offboard_precland_controller` — sẽ có 2 controller
> tranh nhau bơm setpoint. (Bản quy trình cũ của tôi sai đúng chỗ này.)

Bay (trong `pxh>` của T1):
```
pxh> commander takeoff
     # đợi lên độ cao, monitor hiện DRONE -> FLIGHT_IN_PROGRESS
pxh> commander land
     # controller bắt được AUTO.LAND -> tự chuyển OFFBOARD -> GOTO_BOX
```

##### Tiêu chí Pass (driver tự chấm)

`m3_full_loop_monitor.py` **chỉ nghe, không publish, không gọi service nào** —
nên kết quả PASS không thể là sản phẩm phụ của việc harness tự kích thích hệ
thống (đúng bài học rút ra từ 6b).

1. FSM drone đi đủ `GOTO_BOX→PRELANDING_CHECK→WAIT_BOX_READY→START`
2. Drone tới `DONE`
3. FSM box đi đủ `EMPTY→PREPARING_FOR_LANDING→WAITING_FOR_LANDING→SECURING_DRONE`
4. **Box rời `EMPTY` SAU khi drone vào `WAIT_BOX_READY`** → chứng minh chính
   `REQUEST_LANDING` của drone gây ra, không phải trigger tay còn sót
5. **Drone vào `START` SAU khi box đạt `WAITING_FOR_LANDING`** → không chạy
   trước nắp box
6. Box đạt `SECURING_DRONE` sau khi land detector thật báo `ON_GROUND`
7. GPS box khác 0 (fixture B2 đang chạy)

Ctrl+C ở T7 để in báo cáo.

##### Kết quả lần 1 (2026-07-22) — bắt tay ✅ 7/7, hạ cánh thị giác ❌

```
[   31.6s] DRONE  -> FLIGHT_IN_PROGRESS
[   44.1s] DRONE  -> GOTO_BOX
[   45.1s] DRONE  -> PRELANDING_CHECK
[   45.1s] DRONE  -> WAIT_BOX_READY
[   45.3s] BOX    -> IDLE(1)
[   45.5s] BOX    -> PREPARING_FOR_LANDING(6)
[   45.7s] BOX    -> WAITING_FOR_LANDING(7)
[   45.7s] DRONE  -> START
[   50.8s] DRONE  -> SEARCH
[   80.9s] DRONE  -> FALLBACK          <-- 30s SEARCH, không thấy marker
[   94.9s] MAVROS -> landed_state=ON_GROUND
[   95.1s] BOX    -> SECURING_DRONE(8)
```
Cả 7 tiêu chí của monitor đều PASS, gồm 2 tiêu chí nhân quả then chốt:
- Box rời `EMPTY` @45.50s **sau** khi drone vào `WAIT_BOX_READY` @45.12s
- Drone vào `START` @45.72s **sau** khi box báo `WAITING_FOR_LANDING` @45.70s

→ **Phần M3 (bắt tay) đạt.** Phần hỏng là hạ cánh thị giác, nguyên nhân nằm
ngoài logic M3.

##### Nguyên nhân gốc: sai số ngang 4.2 m > tầm phủ dọc của camera

Camera (`Tools/simulation/gz/models/gimbal/model.sdf`):
`horizontal_fov 1.4137` rad (81°), 1280×720 → **vFOV chỉ 51.3°**.
Nửa tầm phủ **dọc** = `alt × 0.48` (không phải × 0.85 như tầm ngang).

Hai sai số cộng dồn:
| Nguồn | Sai số |
|---|---|
| `y_anten_gps_offset: 1.9` — box_info lệch bắc so với marker | 1.9 m |
| `goto_box_arrival_radius: 3.0` — drone dừng khi *còn cách box 3 m*, rồi `handshake_hold_ = pos_enu_` đóng băng luôn chỗ đó | tới 3.0 m |

Vị trí thật (tính từ log + world sdf):
```
box_info báo về : lat 47.39795671 lon 8.54621469  ->  ENU (3.84, -1.60)
marker thật     : world sdf pose                  ->  ENU (4.00, -3.50)
drone hover ở   : ~ENU (1.07, -0.45)   (dừng cách box_info 3 m)
=> khoảng cách drone -> marker = 4.23 m
```
Đối chiếu tầm phủ dọc:

| Độ cao | Nửa tầm phủ dọc | Marker lệch 3.05 m nam |
|---|---|---|
| 8.8 m | 4.23 m | vừa mép |
| 8.0 m | 3.84 m | sát mép |
| **6.0 m** | **2.88 m** | ❌ **ra khỏi khung** |

`START` hạ độ cao dần → marker rơi khỏi khung và ở ngoài suốt 30 s `SEARCH`.
Khớp chính xác với log tracker: `No fractal marker yet: frames=2596...3084`
(tracker chạy tốt, xử lý 5-9 ms — vấn đề là marker không nằm trong khung).

##### 3 điểm đã sửa

**S1. `handshake_hold_` giữ tại vị trí BOX, không phải vị trí lúc chạm bán kính.**
```cpp
// cũ:  handshake_hold_ = pos_enu_;          // đóng băng chỗ cách box tới 3 m
// mới: handshake_hold_ = Vector3{box_east, box_north, goto_box_alt_};
```
Biến thời gian hover bắt tay (5-30 s) thành **thao tác căn tâm cuối cùng** —
loại bỏ toàn bộ 3 m dung sai của bán kính tới nơi.

**S2. Zero offset antenna cho SITL** (`box_state_manager.yaml`), giữ comment
giá trị thật:
```yaml
x_anten_gps_offset: 0.0   # real hardware value: -0.15
y_anten_gps_offset: 0.0   # real hardware value: 1.9
z_anten_gps_offset: 0.0   # real hardware value: -1.5
```
`box_gps_publisher.py` đã publish thẳng tâm pad nên không cần offset nữa.

**S3. Vá cổng `PRELANDING_CHECK` rỗng.**
Lần 1, `PRELANDING_CHECK → WAIT_BOX_READY` xảy ra trong **cùng 0.1 s** — vì
`gimbal_configured_` chỉ có nghĩa *"đã gửi lệnh gimbal"*, không phải *"gimbal
đã cụp xuống"*. Thêm kiểm tra `camera_ok`: `/gimbal_camera/camera_info` phải
còn sống trong 3 s.
> Trung thực: `camera_ok` **không** bắt được lỗi lần 1 (camera vẫn sống, lỗi là
> hình học). Nó chặn trường hợp khác — cầu ảnh gz chết — để không bắt box mở nắp
> cho một drone mù. Không cổng nào ở đây chứng minh được marker nằm trong khung;
> đó là việc của `START`/`SEARCH`, và S1 chính là thứ đảm bảo vào `START` ở đúng
> tâm.

Sai số ngang còn lại sau S1+S2: **≈0 m** (thay vì 4.23 m).

##### Sửa tiếp sau 7b (2026-07-22)

**Đồng bộ overlay pose ↔ ảnh — ✅ đã verify**
Overlay vẽ `last_uav_pose_` (pose *mới nhất*) lên ảnh có nội dung *cũ hơn* →
`UAV ENU U` và `MARKER DIST` trong cùng một khung hình đến từ hai thời điểm khác
nhau. Sửa: giữ lịch sử pose 5 s + `poseAt(stamp)` chọn mẫu gần timestamp ảnh
nhất, lưu vào member `frame_pose_` dùng chung cho **cả overlay lẫn cổng
`acceptPose()`** (cổng này so `tvec.z` với UAV z nên cũng bị lệch).

> ⚠️ **Bẫy suýt làm hỏng thêm:** tracker chạy `use_sim_time: True` (sim time)
> nhưng MAVROS ở T2 chạy **wall clock**. Stamp chênh ~1.78e9 → bản `poseAt()`
> đầu tiên sẽ chọn mẫu **cũ nhất** trong buffer, **tệ hơn cả trước khi sửa**.
> Đã thêm guard: lệch > 5 s thì fallback về pose mới nhất và in
> `sync N/A: clock mismatch` màu đỏ.

Verify bằng `m3_box_handshake_test/overlay_sync_test.py` (bơm ảnh có stamp cũ
hơn pose mới nhất 2 s, hai pose `U=9.0` khớp ảnh vs `U=2.0` mới nhất):

| Kịch bản | Overlay vẽ | Kết quả |
|---|---|---|
| A — cùng clock | `UAV ENU: E=4.00, N=-3.50, U=9.00` (trắng) | ✅ chọn pose khớp ảnh |
| B — lệch clock | `UAV ENU: E=4.00, N=-3.50, U=2.00` (đỏ) | ✅ fallback + cảnh báo |

> Muốn overlay đồng bộ thật ở 7c: thêm `use_sim_time:=true` cho MAVROS ở T2.
> Khi đó sẽ thấy `(sync ~20ms)` màu trắng thay vì đỏ.

**Marker về đúng 50 cm phần đen**
Quy ước chốt từ source aruco 3.1.12 (`fractalmarkerset.cpp:703`):
`marker_size` = cạnh **marker đen ngoài cùng**, không tính viền trắng.
→ plane pad đổi `0.50` → **`0.6241`** (vì `0.6241 × 0.8012 = 0.5000`),
`marker_size` giữ `0.50` (giờ mới đúng nghĩa).

Viền trắng của `marker.png` đo được **đúng 1 module**:
```
1197 px tổng, đen 959 px, viền (1197-959)/2 = 119 px
id0 = 36 bits = lưới 6x6, + viền đen 1 module mỗi bên = 8 module
959 / 8 = 119.9 px/module   ->  viền trắng 119 px = 1 module
```
1 module là quiet zone tối thiểu ArUco khuyến nghị → **không được cắt bớt**,
hỏng nặng nhất ở độ cao lớn khi mỗi module chỉ còn vài pixel. Nếu M3.5 thiếu
chỗ thì thu nhỏ *toàn bộ* marker theo tỉ lệ, hoặc làm sàn lòng box màu sáng để
vành sáng đến từ bề mặt thay vì từ texture.

##### Lỗi thao tác cần tránh
Xem `/siyi/fractal_debug` trong rqt sẽ **trống** — đó là topic của camera phần
cứng SIYI thật, SITL không có. Topic đúng (theo remap trong
`sitl_precland.launch.py`): **`/landing/annotated_image`**.

##### Kết quả lần 2 (2026-07-22) — ✅ PASS toàn bộ

```
[   48.5s] DRONE  -> GOTO_BOX
[   48.7s] DRONE  -> PRELANDING_CHECK
[   48.7s] DRONE  -> WAIT_BOX_READY
[   49.0s] BOX    -> PREPARING_FOR_LANDING(6)
[   49.4s] BOX    -> WAITING_FOR_LANDING(7)
[   49.4s] DRONE  -> START
[   50.5s] DRONE  -> HORIZONTAL_APPROACH
[   50.7s] DRONE  -> DESCEND_ABOVE_TARGET
[   76.4s] DRONE  -> FINAL_APPROACH
[   77.7s] DRONE  -> IDLE            (qua DONE, xem ghi chú bên dưới)
[   77.8s] MAVROS -> landed_state=ON_GROUND
[   78.0s] BOX    -> SECURING_DRONE(8)
```

**Độ chính xác ước lượng marker của tracker:**
```
FINAL_APPROACH: final_xy=(3.97,-3.50)
marker thật (world sdf) = (4.00,-3.50)
=> lệch 3 cm
```
Cũng khớp với overlay: `TGT ENU: E=3.96, N=-3.52`.
S1+S2 đã đưa **sai số căn tâm** (drone vào START cách tâm bao xa) từ
**4.23 m → 0.03 m** — đó là thứ khiến marker luôn nằm trong khung, không phải
sai số hạ cánh.

> ⚠️ **`final_xy` là điểm NGẮM, không phải vị trí drone.** "3 cm" ở đây là độ
> lệch giữa ước lượng marker của tracker và marker thật, KHÔNG phải drone đậu
> cách marker bao xa. Sai số hạ cánh THẬT chỉ đo được từ M3c (`TOUCHDOWN`):
> **4.9 cm**. Xem khối "Kết luận & số liệu chính xác" ở đầu M3.

Khoá yaw 2 tầng chạy đúng thiết kế qua đường bắt tay mới:
```
Entering Stage 2 Yaw Lock at 3m
[YAW-LOCK] latched target=-1.6 deg from 30 samples at 3.0m
YAW-ALIGN & RE-CENTERING COMPLETE [Stage 2] — continuing descent
```

##### Sửa tiêu chí "Drone reached DONE" — lỗi đo của driver

Lần 2 monitor báo FAIL đúng 1 tiêu chí, nhưng đó là **lỗi harness**, không phải
lỗi sản phẩm:
```
FSM: FINAL_APPROACH → DONE   @291.469
FSM: DONE → IDLE             @291.502
```
`DONE` chỉ tồn tại **33 ms** (cả 2 chuyển tiếp nằm trong cùng 1 tick điều khiển),
trong khi `/lander/state` publish ~10 Hz → observer thụ động **không thể** lấy
mẫu được. Cùng loại lỗi với metric fidelity của 6b.
*Cách sửa:* tiêu chí nhận bằng chứng tương đương — `FINAL_APPROACH` đã đạt **và**
trace kết thúc ở `IDLE` (từ `FINAL_APPROACH` chỉ tới được `IDLE` qua `DONE`).

##### Giải đáp: `MARKER DIST` vs `UAV ENU U` lệch nhau

`get_alt() = pos_enu_.z - virtual_pad_z_` với `virtual_pad_z_ = 0.0`
→ **`alt` trong log và `U` trong overlay là cùng một đại lượng.**

Ghép 10 cặp có timestamp từ log (tracker tvec z ↔ DESCEND alt):

| t | tvec z | alt | alt − tvec |
|---|---|---|---|
| 280.3 / 280.5 | 2.95 | 2.99 | 0.04 |
| 281.3 / 281.5 | 2.81 | 2.97 | 0.16 |
| 283.3 / 283.5 | 2.62 | 2.71 | 0.09 |
| 285.3 / 285.5 | 1.84 | 1.94 | 0.10 |
| 287.4 / 287.5 | 1.14 | 1.25 | 0.11 |
| 289.4 / 289.5 | 0.39 | 0.52 | 0.13 |

Chênh lệch **rất ổn định 0.09–0.16 m**. Mẫu `alt` lấy sau mẫu `tvec` ~0.15 s,
drone đang hạ 0.3–0.4 m/s nên tụt thêm ~0.06 m; bù lại → offset thật ≈ **0.17 m**
= đúng cao độ mặt marker (`marker_visual` pose z = **0.172**).

→ **Tracker chuẩn, không có sai số thang đo.** Quan hệ đúng là
`tvec_z = alt − 0.172`.

Riêng ảnh chụp overlay (`U=2.53` vs `DIST=3.11`, lệch 0.75 m) **không khớp** quan
hệ trên: `tvec 3.11` ứng với `alt 3.28`, còn `U=2.53` ứng với `tvec 2.36` — hai
số cách nhau ~0.75 m độ cao ≈ **2 giây** hạ độ cao. Tức khối `UAV ENU` và khối
`CAM TVEC` trong overlay **được vẽ từ hai thời điểm khác nhau** → lỗi đồng bộ
hiển thị, không phải lỗi dẫn đường. Bằng chứng phủ định: 10 cặp có timestamp ở
trên đều cho 0.17 m, và sai số hạ cánh thật chỉ 3 cm.

##### Phát hiện tồn đọng cho M3.5: marker.png có viền trắng 20%

```
marker.png = 1197x1197 px
vùng marker đen chiếm 80.12% mỗi chiều
=> marker vật lý = 0.50 x 0.8012 = 0.4006 m, KHÔNG phải 0.50 m
```
Nhưng `aruco_fractal_tracker_node.cpp:97` truyền
`detector_.setParams(cam_params, marker_size_)` với `marker_size: 0.50`.

Thực nghiệm cho thấy thang đo **gần đúng** (sai số dư ~4–5%, xem bảng trên), nên
quy ước `marker_size` của thư viện fractal ở đây rõ ràng **bao gồm cả viền
trắng**, không phải chỉ vùng đen. Không cần sửa ngay.

> ⚠️ **Phải chốt quy ước này trước khi làm M3.5.** M3.5 sẽ chuyển marker sang
> thân box và có thể phải thu nhỏ (lòng box chỉ ≈0.69 m). Nếu lúc đó đặt
> `marker_size` theo vùng đen thay vì theo cả tấm plane, sẽ sinh sai số thang đo
> ~25% → sai độ cao ước lượng. Đây chính là rủi ro mức Cao đã ghi trong
> `M3_5_PLAN.md`, giờ đã có số liệu cụ thể.

##### Lưu ý khi chạy lại
Sau 1 vòng box ở `CHARGING`, sẽ **từ chối** `REQUEST_LANDING` (chỉ nhận khi
`EMPTY`) → restart T3. Log `BoxLink` sẽ hiện:
```
BoxLink: REQUEST_LANDING rejected (box_state=9, expected EMPTY=0). Retrying.
```

---

### M3b — Hợp nhất world Gazebo (marker trên thân box)

**✅ HOÀN THÀNH (2026-07-22).** Kế hoạch, nhật ký bẫy và kết quả đầy đủ:
**`M3_5_PLAN.md`**.

#### Thay đổi code (2026-07-22)

| # | Thay đổi | File |
|---|---|---|
| P1.1 | Gỡ `<include>` `dib_box_landing_pad` khỏi world (kèm hướng dẫn khôi phục trong chú thích) | `Tools/simulation/gz/worlds/fractal_aruco_landing.sdf` |
| P1.2 | Launch mới: spawn box vào gz server **đang chạy** thay vì tự dựng world riêng; `z=0.78233` (tính từ collision, không đoán), `(2.5, −2.0)` | `box_simulation/launch/box_spawn_only.launch.py` |
| P1.3 | `TimerAction(20 s)` + **mỗi controller một tiến trình `spawner`** | cùng file |
| P2.3 | Marker tách thành model SDF riêng, spawn cùng launch tại pose suy ra từ pose box | `Tools/simulation/gz/models/dib_box_marker/`, `box.xacro` |
| P2.6 | Fixture GPS trỏ về marker `(2.5129, −2.5896)` → lat 47.397947795 / lon 8.546197088 | `docs/m3_box_handshake_test/box_gps_publisher.py` |
| — | Đóng gói: model + world vào `px4/Tools/simulation/gz/`, launch vào `overlays/box_simulation/` | repo `SITL_PrecisionLanding` |

#### 4 bẫy đã gặp và cách sửa

**B1. Segfault gz server khi spawn box — nạp nhầm `gz_ros2_control`.**
```
#1 ~/gz_ros2_control_ws/.../libgz_ros2_control-system.so
     Configure(..., gz::sim::v8::EntityComponentManager&, ...)   <- Harmonic
#0 /opt/ros/humble/lib/libgz_hardware_plugins.so
     initSim(..., ignition::gazebo::v6::EntityComponentManager&) <- FORTRESS
```
Plugin **system** (Harmonic) nạp đúng, nhưng khi nó nạp tiếp plugin **hardware**
qua pluginlib thì vớ phải bản **apt Fortress**. Điểm dễ nhầm: hai plugin tìm
theo hai đường khác nhau — system qua `GZ_SIM_SYSTEM_PLUGIN_PATH`, hardware qua
pluginlib (`AMENT_PREFIX_PATH` + `LD_LIBRARY_PATH`). Nên `export
GZ_SIM_SYSTEM_PLUGIN_PATH` **không đủ**.
*Sửa:* `source ~/gz_ros2_control_ws/install/setup.bash` ở terminal chạy `make`,
hoặc gỡ hẳn `sudo apt remove ros-humble-gz-ros2-control`
(`apt-cache rdepends --installed` cho kết quả rỗng).

**B2. Box spawn xong nhưng VÔ HÌNH.**
```
[Err] Unable to find file with URI [model://box_simulation/meshes/dae/...]
[Err] Failed to load geometry for visual: base_link_visual
```
Nhưng `gz model --list` **có** `Box`, 6 joint nạp đủ, 4 controller configure
xong — chỉ phần nhìn rỗng. Nguyên nhân:
`SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', ...)` trong launch chỉ áp cho
tiến trình con của **chính launch đó**, còn thứ phân giải `model://` là **gz
server** do PX4 khởi động ở terminal khác.
*Sửa:* export ở terminal chạy `make`, trước `make`:
```bash
export GZ_SIM_RESOURCE_PATH=$HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share
```
An toàn vì PX4 **nối thêm** chứ không ghi đè
(`src/modules/simulation/gz_bridge/gz_env.sh.in:19`).

> B1 và B2 **cùng một lỗi**: đặt env đúng giá trị nhưng **sai tiến trình**.
> Quy tắc rút ra: env nào gz server cần thì đặt ở terminal chạy `make px4_sitl`,
> không bao giờ ở launch file spawn.

**B3. Controller không active — timeout cold start.**
`controller_manager` nằm trong plugin gz, chỉ khởi động khi box được spawn. Gọi
`load_controller` ngay lúc đó bắt gặp nó đang khởi tạo và phản hồi mất ~15 s,
trong khi cả `ros2 control load_controller` lẫn `spawner` đều hard-code timeout
**10 s** cho lời gọi service ở Humble:
```
667.76  gz_ros2_control: Loading controller_manager
667.99  controller_manager: Loading controller 'joint_state_broadcaster'
683.16  controller_manager: (retry) already loaded
```
`spawner --controller-manager-timeout` **không giúp** — nó chỉ giới hạn thời
gian chờ service **xuất hiện**, không phải thời gian của lời gọi.
*Sửa:* `TimerAction(period=20.0)` + **một `spawner` cho mỗi controller** (gộp 4
vào một spawner khiến cái đầu lỗi là ba cái sau không được thử — đây là hồi quy
do chính tôi tạo ra rồi phải sửa lại).
*Xử lý thủ công nếu vẫn còn `unconfigured`* (nó **đã nạp**, chỉ mất nửa sau) —
phải **hai bước**, vì `unconfigured → active` không phải chuyển trạng thái hợp lệ:
```bash
ros2 control set_controller_state joint_state_broadcaster configure
ros2 control set_controller_state joint_state_broadcaster active
```

**B4. Marker không hiện — `<visual>` trong `<gazebo reference>` bị NUỐT.**
Cách hiển nhiên (đặt `<visual>` vào `<gazebo reference="base_link">` của
`box.xacro`) **trông đúng và hỏng im lặng**. sdformat bóc bỏ lớp vỏ `<visual>`
rồi trộn các con vào `base_link_visual` đã có sẵn:
```xml
<visual name='base_link_visual'>
  <pose>0 0 0 0 0 0</pose>
  <geometry><mesh><uri>...BOX PAD1.0_simple.dae</uri></mesh></geometry>
  <pose>0.0129 -0.1456 0.5896 -1.5708 0 0</pose>    <!-- pose THỨ HAI -->
  <geometry><plane><size>0.6241 0.6241</size></plane></geometry>
```
Một `<visual>` chỉ được có một `<pose>` và một `<geometry>`; cái đầu thắng,
plane bị vứt — không lỗi, không cảnh báo. Đo được: URDF chứa
`landing_marker_visual` **1 lần**, `gz sdf -p` cho ra **0 lần**. URDF cũng
không có kiểu `<plane>` lẫn PBR `albedo_map`, nên marker này về nguyên tắc
không diễn đạt được trong URDF.
*Sửa:* model SDF riêng `dib_box_marker` (plane 0.6241 m, `<static>`, **không
collision** để không làm land detector báo sớm), spawn cùng launch tại pose
**suy ra từ** pose box:
```
MARKER = (SPAWN_X + 0.0129, SPAWN_Y − 0.5896, SPAWN_Z − 0.1456)
       = (2.5129, −2.5896, 0.63673)
```
trùng khít `PAD_EAST/PAD_NORTH` của fixture GPS — dời box thì marker và fixture
tự đi theo.

> Bài học: **suy luận về sdformat phải kiểm bằng `gz sdf -p`, không bằng lập
> luận.** Và B2 che mất B4 — trước khi sửa resource path thì marker chắc chắn
> không hiện, nên mọi kết luận về `<gazebo reference>` đưa ra lúc đó đều sẽ sai.

#### 7c — vòng kín trên world hợp nhất ✅ PASS 7/7

Quy trình chạy đầy đủ: **mục 4 của `README.md`** (đã đóng gói để người khác
chạy lại được), hoặc mục "QUY TRÌNH CHẠY LẠI M3.5 TỪ ĐẦU" trong `M3_5_PLAN.md`.
Tóm tắt: giai đoạn A 2 terminal dựng world + kiểm box/marker; **chỉ khi A xanh
hết mới sang** giai đoạn B thêm 4 terminal. Chạy 7c trên marker không hiện thì
chắc chắn fail.

Khác 7b ở đúng một chỗ quan trọng: **`mock_hw_stub.py` bị thay bằng
`box_hardware_adapter_node`**. Không chạy cả hai — sẽ có hai bên cùng trả lời
một service.

> **Quy trình đã đổi từ 2026-07-23** (bản gốc dùng 9 terminal, gọi từng node):
> ba node phía box gom vào `dib_bringup.launch.py`, MAVROS dùng
> `sitl_mavros.launch.py`, fixture SITL tách sang `sitl_fixtures.launch.py`.
> Còn **6 terminal**. Bảng lệnh hiện hành ở `M3_5_PLAN.md` hoặc README mục 4.

```
[   42.4s] DRONE  -> GOTO_BOX
[   44.0s] DRONE  -> PRELANDING_CHECK -> WAIT_BOX_READY
[   44.3s] BOX    -> PREPARING_FOR_LANDING(6)
[   44.7s] BOX    -> WAITING_FOR_LANDING(7)
[   44.8s] DRONE  -> START -> HORIZONTAL_APPROACH -> DESCEND_ABOVE_TARGET
[   74.7s] DRONE  -> FINAL_APPROACH
[   77.0s] MAVROS -> landed_state=ON_GROUND
[   77.1s] BOX    -> SECURING_DRONE(8)
```
Không có `SEARCH`, không có `FALLBACK` — khác hẳn 7b lần 1, nơi drone tìm
marker 30 s rồi bỏ cuộc.

Ba số liệu quan trọng hơn cả 7 tiêu chí:
- **Sai số ước lượng marker của tracker 4.0 cm**: `final_xy=(2.54, −2.56)` so
  với marker `(2.5129, −2.5896)`.
  > ⚠️ **Đính chính 2026-07-23.** Con số này ban đầu ghi là "sai số hạ cánh" —
  > **sai**. `final_xy` là `final_x_/final_y_`, tức **điểm ngắm** (ước lượng
  > marker từ tracker, đặt ở `offboard_precland_controller.cpp:1049-1050`),
  > không phải vị trí drone. Vị trí chạm đất thật khi đó **không được ghi ở
  > đâu**. Từ M3.6 đã có dòng `TOUCHDOWN` in cả hai.
- **Drone đậu trên sàn box**: `alt=0.602…0.628 m` khớp `MARKER_Z=0.63673`.
  Dòng `Ground contact: blocked by 20.5cm → force-disarm` là hệ quả đúng, không
  phải lỗi.
- **Che khuất không ảnh hưởng tracker**: fractal rụng tầng theo độ cao đúng
  thiết kế (`ids=[0,1,2]` ở trên cao → `ids=[1,2]` ở 0.65 m).

Cơ cấu box **thật** đã chạy — `box_hardware_adapter_node` thay hẳn
`mock_hw_stub.py`, điều khiển đúng khớp Gazebo: mở nắp 1.570 rad → nhả kẹp →
(sau khi đáp) kẹp ngang 0.200 m → kẹp dọc 0.200 m → đóng nắp 0.000 rad.

**Lộ ra:** `box_state_manager` dừng ở `SECURING_DRONE` securing state 5,
`Waiting for drone to request power off` — phía drone chưa có bước yêu cầu
power-off sau disarm. Chuỗi kẹp/nắp đã xong; đây là mảnh thiếu của vòng đời
đầy đủ, không phải lỗi M3.5. → **Đã xử lý ở M3.6.**

<details><summary>Bối cảnh ban đầu của M3.5</summary>

Chèn giữa M3 và M4. Lý do tồn tại: ở 7b, box và drone chạy **2 tiến trình
Gazebo, 2 world tách biệt** — drone hạ xuống `dib_box_landing_pad` (tĩnh, chỉ
có visual, có marker) trong khi nắp/kẹp cử động ở world khác của
`box_simulation` (có joint, **không có marker**). M3.5 gộp hai nửa đó.

**Không phải điều kiện để M3 đúng** — 7b đã đủ chứng minh logic phần mềm.
M3.5 phục vụ sản phẩm đóng gói: video drone bay tới → box mở nắp → drone hạ
vào trong → kẹp đóng, trong một world duy nhất.

2 rủi ro mức Cao đã lường trước (chi tiết trong `M3_5_PLAN.md`):
- `marker_size` param lệch kích thước plane thật → sai **thang đo** pose → sai
  độ cao → flare sớm hoặc đâm xuống.
- Quên gỡ `dib_box_landing_pad` khỏi world → **2 marker fractal giống hệt
  nhau**, tracker bám nhầm, drone hạ xuống pad tĩnh thay vì vào lòng box —
  mà mọi thứ vẫn *trông như* đang chạy đúng.

Ước lượng: nửa ngày → 1 ngày.

</details>

---

### M3c — Khép vòng đời tới `CHARGING`

**✅ PASS 8/8 (2026-07-23).**

#### Vấn đề

Sau M3.5, chuỗi chạy đúng tới đây rồi **kẹt**:
```
drone hạ cánh → disarm ✅
box: SECURING_DRONE → kẹp ngang → kẹp dọc → đóng nắp ✅
box: "Waiting for drone to request power off"      ← đứng yên mãi
```
Box đã giữ drone nhưng không sang được `CHARGING` vì đang chờ drone gửi
`TURN_OFF_DRONE` — mà phía drone **chưa bao giờ gửi**. Nó chỉ thoát được qua
fallback 5 s "telemetry drone nguội", tức bằng cách drone *có vẻ như biến mất*.

#### Phát hiện: nhánh FSM đã có sẵn, chỉ thiếu bên gọi

Toàn bộ phía box đã tồn tại từ trước, **không sửa một dòng nào** của FSM:

| Thứ | Ở đâu |
|---|---|
| Sub-state `WAITING_DRONE_REQUEST_POWER_OFF`, `POWER_OFF` | `securing_state_manager.hpp:15-16` |
| Hằng `TURN_OFF_DRONE = 4` | `dib_msgs/msg/BoxCmd.msg` |
| Box nhận lệnh → set cờ `request_poweroff` | `box_state_manager.cpp:310-312` |
| Sub-FSM tiêu thụ cờ → `POWER_OFF` | `securing_state_manager.cpp:208-211` |
| `POWER_OFF → DONE` khi telemetry im 5 s | `securing_state_manager.cpp:217-220` |

Comment `// Implement the logic for waiting for the drone to request power off`
ở `securing_state_manager.cpp:101` vẫn còn nguyên dạng TODO — dấu hiệu nhánh
này chưa từng chạy đúng.

#### Thay đổi code

| Thành phần | Thay đổi |
|---|---|
| `BoxLink::request_power_off()` | Gửi `TURN_OFF_DRONE`, idempotent + retry 3 s, **gated trên `box_state == SECURING_DRONE`** — ngoài cửa sổ đó box bỏ qua trong im lặng |
| `st_done()` | Giữ ở `DONE` chờ box tới `CHARGING`, timeout `power_off_timeout_sec: 90.0` |
| `box_hardware_adapter` | Publish `/dock/drone_power` (latched) khi nhận `/dock/power_button/cmd` |
| `mavros_to_dib_telemetry` | Ngừng publish khi rail = false |

#### Mảnh ẩn: phải mô phỏng cú cắt điện

Chỉ thêm `TURN_OFF_DRONE` là **chưa đủ**. `POWER_OFF → DONE` chỉ xảy ra khi
telemetry drone **im lặng quá 5 giây**. Trên phần cứng thật, box cắt nguồn →
máy tính đồng hành tắt → im lặng, miễn phí. Trong SITL, MAVROS chạy mãi →
**box kẹt ở `POWER_OFF` vĩnh viễn**.

Nên adapter báo trạng thái rail và cầu telemetry ngừng phát khi nhận `false` —
bắt chước đúng hành vi máy tính mất điện.

> **Xác nhận không dùng service response.** `box_cmd_callback()` đặt
> `response->success = true` **ở dòng đầu tiên** (`box_state_manager.cpp:210`)
> rồi mới giao việc cho thread rời — phản hồi được gửi trước khi có gì được
> đánh giá, nên **không mang thông tin**. `BoxLink` xác nhận bằng
> `box_state == CHARGING` thay vì bằng reply. Cũng vì lý do này,
> `landing_request_accepted()` của M3 luôn true khi chạy với box thật; xác nhận
> thật là box rời `EMPTY`, thứ mà `is_ready()` bắt đúng.

#### Quy trình chạy

Y hệt 7c (6 terminal — xem `M3_5_PLAN.md` hoặc README mục 4), **không thêm
terminal nào**. Khác duy nhất: sau khi drone chạm đất phải **chờ thêm ~35–40
giây** rồi mới Ctrl+C, vì box còn kẹp + đóng nắp trước khi xử lý lệnh tắt
nguồn.

#### Kết quả (2026-07-23)

```
[   77.9s] DRONE  -> WAIT_BOX_READY
[   78.3s] BOX    -> PREPARING_FOR_LANDING(6)
[   81.3s] BOX    -> WAITING_FOR_LANDING(7)
[   81.3s] DRONE  -> START -> HORIZONTAL_APPROACH -> DESCEND_ABOVE_TARGET
[  105.6s] DRONE  -> FINAL_APPROACH
[  107.3s] DRONE  -> DONE
[  111.2s] MAVROS -> landed_state=ON_GROUND
[  111.3s] BOX    -> SECURING_DRONE(8)
[  126.6s] BOX    -> CHARGING(9)          <-- M3.6
[  126.6s] DRONE  -> IDLE
```

Trace log đầy đủ chuỗi nhân quả:
```
BoxLink: box_state 7 -> 8
BoxLink: sending TURN_OFF_DRONE to b2 (agent_id=12)
/dock/power_button/cmd command=0 -> drone power OFF
Dock power OFF: stopping publishing d1/telemetry
BoxLink: box reached CHARGING - drone secured and powered off
Box reached CHARGING — drone-in-a-box cycle complete
```

`TURN_OFF_DRONE` gửi lặp mỗi 3 giây (4 lần) là **đúng thiết kế**: lệnh
idempotent, box giữ như cờ dính và chỉ tiêu thụ khi kẹp/nắp đã đóng xong.

Monitor: **8/8**, tiêu chí mới là `Box reached CHARGING`.

#### Tác dụng phụ: `DONE` giờ đo được

Trước M3.6, `DONE` chỉ tồn tại **33 ms** nên monitor không lấy mẫu kịp (tiêu
chí 2 của 7b phải nới lỏng). Giờ `DONE` kéo dài ~35 s → đo trực tiếp được.

#### Lỗi lộ ra và đã sửa — `CHARGING` không thực sự sạc

```
1784779263.132719  box_hardware_adapter  /dock/charge/cmd command=1 (stub)
1784779264.132612  box_state_manager     [ERROR] Failed to send charge command
                   ^^^ đúng 1.000 s sau
```
Adapter **nhận và trả lời**, nhưng box vẫn báo thất bại sau đúng 1,000 s.

*Nguyên nhân:* `chargingState()` (`box_state_manager.cpp:725-728`) gọi
`charge_cmd(1)` **trực tiếp trong timer callback**, mà `charge_cmd()` chặn bằng
`result.wait_for(1s)` (`box_state_manager.cpp:803`). Executor bị khoá trong
chính callback đó → không xử lý được response → hết 1 s → lỗi.

*Bằng chứng là bất nhất nội bộ, không phải thiết kế:* mọi call site khác trong
codebase đều bọc `std::thread(...).detach()` —
`preparing_state_manager.cpp:179,208`, `securing_state_manager.cpp:27,47,66,85`.
Đó chính là lý do lid/clamp/power chạy được, riêng charging thì không.

*Sửa:* bọc theo đúng khuôn mẫu đó. Kiểm bằng
`grep 'Charge command' /tmp/bringup.log` → phải thấy `Charge command sent`,
không còn `Failed to send charge command`.

---

### M3d — Dọn log + báo vị trí chính xác

Không phải milestone — nhưng chặn mọi việc sau, vì terminal ngập tới mức không
lần ra lỗi và các dòng báo vị trí đang nói sai về thứ chúng báo cáo.

#### Độ ồn log

| Nguồn | Trước | Sau |
|---|---|---|
| `box_state_manager` | **10–30 dòng/giây** (in mọi tick của timer 100 ms) | 3 dòng / 12 giây |
| `aruco_fractal_tracker` | ~3 dòng/giây | in khi `tracking_state_` đổi + throttle 5 s |
| `offboard_precland_controller` | ~2 dòng/giây | giữ (đều là chuyển FSM) |

`box_state_manager` chiếm **gần 100%** độ ồn của terminal `dib_bringup` — ba
node còn lại chỉ in khi có sự kiện thật.

*Cách sửa:* cờ `change_state` **đã tồn tại** trong file và đúng nghĩa cần dùng —
`runStateMachine()` đặt `true` đúng tick đổi state, `false` các tick còn lại
(`box_state_manager.cpp:365-378`). Chỉ cần chuyển dòng log vào trong cờ đó.

Hai chỗ cần xử lý riêng:
- **Sub-FSM** (`PreparingStateManager`, `SecuringStateManager`) tự tiến theo
  nhịp riêng, nên `change_state` một mình chỉ báo được **bước đầu tiên**. Thêm
  biến nhớ sub-state trước đó và so sánh, giống cách `runStateMachine` làm với
  `box_state_`. Bộ nhớ reset cùng lúc với chuyển state cha.
- **State khởi động** không được báo, vì `box_state_` khởi tạo là `EMPTY` nên
  tick đầu không tính là "đổi". Thêm cờ `logged_any_state_`.
  > Đây là hồi quy do chính việc gate gây ra, phát hiện khi chạy thử node đơn
  > lẻ 12 giây và thấy thiếu dòng `Box in EMPTY state`.

#### Báo vị trí — 3 lỗi

**1. `final_xy` không phải vị trí drone.** Nó là `final_x_/final_y_` — **điểm
ngắm**, tức ước lượng vị trí marker từ tracker
(`offboard_precland_controller.cpp:1049-1050`, cập nhật ở `1783-1797`). Nhưng
cùng dòng log đó, `alt=` lại lấy từ `pos_enu_.z` — vị trí thật của drone. Đọc
như một toạ độ duy nhất thì sai.

*Sửa:* đổi tên thành `aim`, và thêm `pos_enu_.x/y` vào cùng dòng:
```
FINAL_APPROACH: t=1.2s drone=(2.51,-2.59, alt_agl 0.621m) aim=(2.52,-2.50) ...
```

**2. `alt` mang hai nghĩa trong cùng luồng log.**

| Dòng | Nguồn | Nghĩa |
|---|---|---|
| `[YAW-3D]`, `FINAL_APPROACH` | `pos_enu_.z` | so với điểm cất cánh |
| `APPROACH`, `DESCEND`, `relative_alt` | `get_alt()` | so với marker |

*Sửa:* `alt_agl` và `alt_pad`. Đây chính là gốc của chuyện `UAV ENU U` và
`MARKER DIST` trên HUD trông mâu thuẫn nhau.

**3. Không ghi vị trí chạm đất** → độ chính xác hạ cánh **chưa từng được đo**.

*Sửa:* thêm dòng in ra lúc disarm trong `st_done()`:
```
TOUCHDOWN: drone=(2.5104, -2.5863)  aim=(2.5200, -2.5000)  aim_error=0.090m  alt_agl=0.664m
```
Lấy `drone=` trừ vị trí marker thật `(2.5129, −2.5896)` trong
`box_spawn_only.launch.py` để có sai số so với marker. `aim_error` là chuyện
khác: sai lệch giữa drone và điểm ngắm, tức chất lượng bám của vòng điều khiển.

> ⚠️ **Mọi con số "sai số hạ cánh" ghi trong tài liệu trước 2026-07-23 đều lấy
> từ `final_xy`**, tức là sai số **ước lượng marker của tracker**, không phải
> sai số hạ cánh. Đừng so chúng với `TOUCHDOWN`.

#### `U` vs `MARKER DIST` — chênh lệch là ĐÚNG

Tính lại từ log lần chạy `marker_yaw=90`, nội suy `pos_enu_.z` về đúng thời
điểm chụp ảnh:

| `pos_enu_.z` | `tvec_z` | chênh | tỷ lệ |
|---|---|---|---|
| 2,66 | 2,13 | **0,53** | 1,14 |
| 2,25 | 1,71 | **0,54** | 1,17 |
| 1,75 | 1,27 | **0,48** | 1,32 |
| 1,33 | 0,84 | **0,49** | 1,54 |

Chênh là **hằng số ≈ 0,51 m**, tỷ lệ thì biến thiên mạnh → **lệch gốc quy
chiếu**, và điều đó **loại trừ** khả năng sai `marker_size` (sai thang đo thì
tỷ lệ mới là hằng số). Đó là tin tốt: `marker_size` ảnh hưởng thời điểm flare,
lệch gốc thì không.

Nguồn của 0,51 m, đọc từ model:
```
x500_gimbal/model.sdf:9    gimbal gắn ở  z = +0.28   (TRÊN base_link)
gimbal/model.sdf:265       sensor camera z = -0.162  trong gimbal
                           => camera cao hơn base_link 0.118 m

U − MARKER_DIST = 0.63673 (marker) − 0.118 (camera) = 0.519 m   ✓
```

Kèm theo lộ ra một lỗi config thật: `camera_offset_z = -0.15` (dưới) trong khi
model cho **+0.118** (trên) — sai dấu, lệch 0,27 m. Nhưng nó **chỉ vào TF
`base_link→camera`** (`offboard_precland_controller.cpp:916`), **không** vào
setpoint hạ cánh (setpoint chỉ dùng `x`/`y`, ép `z=0` ở dòng 782-783). Đó là lý
do hạ cánh vẫn đúng. Đã sửa thành `0.118`.

> `camera_offset_x` cũng lệch (config `0.157`, model cho `0.126`) nhưng cái này
> **có** vào setpoint ngang — **chưa đổi**, vì đổi là đổi hành vi hạ cánh đang
> chạy tốt. Cần đo riêng.

#### Đo datum tự động (2026-07-29) — `measure_altitude_datum.py`

Bảng trên nội suy log bằng tay. Để có số liệu chính xác thay vì nhìn log,
`docs/m3_box_handshake_test/measure_altitude_datum.py` ghép cặp
`/mavros/local_position/pose` với `/landing/target_camera` **theo dấu thời gian**
(bỏ cặp lệch > 80 ms) rồi thống kê trên cả đường hạ.

> ⚠️ **Bản đầu của script SAI và đã viết lại.** Nó lấy `uav_z` (độ cao **dọc**)
> trừ `‖tvec‖ = √(x²+y²+z²)` (**cự ly xiên**) — hai đại lượng khác nhau. Khi drone
> ở trên cao và lệch ngang 3 m, cự ly xiên dài hơn độ cao ~1 m, và độ lệch ngang
> đổi suốt chuyến bay nên hiệu của chúng không có giá trị cố định. Nó báo
> "residual 0.371 m không giải thích được" — một tạo tác của phép trung bình một
> xu hướng. Bản mới đo **hai thứ độc lập**: (A) dọc `uav_z − tvec_z` (gimbal giữ
> nadir nên `tvec_z` là cự ly dọc), và (B) ngang `hypot(tvec_x,tvec_y)` so với
> khoảng cách thật tới marker — phép B miễn nhiễm datum, là phép thử scale đúng
> nghĩa. Đã kiểm bản mới bằng dữ liệu tổng hợp có đáp án biết trước (bơm datum
> 0.18 m → báo đúng 0.18; bơm scale −10% → báo `slope 0.90`).

Kết quả lần chạy 2026-07-29 (657–717 mẫu, skew 8 ms trung bình):

| Vùng độ cao | gap_v = uav_z − tvec_z |
|---|---|
| 0.9–2.05 m (**tầm flare**) | **0.506** |
| 2.05–3.20 m | **0.522** ← khớp dự đoán 0.519 |
| 3.20–4.35 m | **0.538** |
| 6.65–7.80 m | 0.366 |
| 8.95–10.1 m | 0.260 |

- **Gần đất `gap_v` = 0.51–0.54 m, khớp hình học 0.519 trong ±2 cm** → datum ≈ 0
  ở đúng vùng quyết định lúc hạ. (Phủ định phỏng đoán "datum 0.18 m" trước đó.)
- `gap_v` co lại trên cao (tương quan −0.91) đi kèm `h_meas` phình ra dù `h_true`
  vẫn nhỏ → **nhiễu pose của fractal ở tầm xa** (trên cao chỉ đọc được marker
  ngoài với vài pixel). **Hội tụ đúng ở tầm flare**, vô hại. Nếu là gimbal nghiêng
  thật thì `gap_v` phải *tăng* trên cao, đây lại giảm — loại trừ.
- Phép **B chưa kết luận** lần này: drone hạ gần thẳng đứng (lệch ngang ≤ 0.36 m),
  chỉ 3 mẫu ≥ 0.3 m. Muốn chốt scale độc lập: bay một lượt **tiến ngang tới box
  từ 4–5 m**.

#### Tách công cụ test khỏi sản phẩm

`dib_bringup.launch.py` từng khởi động `box_gps_publisher.py` nằm trong `docs/`
(gitignore) — công cụ test lẫn trong launch dành cho phần cứng thật. Fixture
chuyển sang `docs/m3_box_handshake_test/sitl_fixtures.launch.py`, cạnh monitor.
`dib_bringup` giờ chỉ còn 3 node sản phẩm và chạy nguyên xi trên phần cứng thật.

#### Kiểm chứng

```bash
ros2 launch precision_landing dib_bringup.launch.py 2>&1 | tee /tmp/bringup.log
wc -l /tmp/bringup.log            # cả chuyến: ~77 dòng, KHÔNG có dòng lặp theo tick
grep 'Box in' /tmp/bringup.log    # mỗi state đúng MỘT dòng
grep 'Charge command' /tmp/bringup.log   # 'sent', không phải 'Failed'
grep -E 'TOUCHDOWN|FINAL_APPROACH' /tmp/precland.log | tail -3
grep -c 'TRACKER\]' /tmp/precland.log   # vài dòng, không phải hàng trăm
```

> Đo thực 2026-07-29: **77 dòng cho cả chuyến ~5 phút**, không dòng nào lặp theo
> tick. Số lặp cao nhất là `SECURING_DRONE sub-state` ×7 = 7 chuyển sub-state
> khác nhau (0→1→…→7), là sự kiện thật. Mốc "dưới 40 dòng" trong plan là cho
> chuyến ~2 phút; điều thật sự cần là **0 dòng lặp theo tick**, đã đạt.

---

## M4 — Tách domain: box và drone trên hai domain, bắc cầu (DDS-Router)

> **KẾT QUẢ HIỆN HÀNH (2026-08-05): cầu mặc định là DDS-Router 2.2.0.**
> `domain_bridge`/`dib_domain_bridge` lùi về làm **phương án dự phòng**. Đọc
> mục "Quay lại DDS-Router" ngay dưới trước, rồi mới tới hai mục lịch sử
> (2026-07-30 bỏ DDS-Router, 2026-08-03 nghiệm thu domain_bridge) — hai mục đó
> giữ nguyên làm hồ sơ, kết luận của chúng đã bị thay thế một phần.
> Topology và tiêu chí Pass **không đổi** qua cả ba lần — chỉ đổi công cụ.

### Quay lại DDS-Router — gỡ đúng hai nút thắt (2026-08-05)

Hai phát hiện mới lật lại kết luận 2026-07-30. Cả hai đo trực tiếp, không suy đoán.

**Nút 1 — `whitelist-interfaces`, không phải lỗi version.** Kết luận cũ "DDS-Router
2.2 cần `ROS_LOCALHOST_ONLY=0`" là *triệu chứng*, không phải nguyên nhân. Bắt gói
multicast bằng socket UDP thường (join `239.255.0.1:7400/7650`, không cần root vì
đây là join multicast bình thường chứ không phải raw capture) cho thấy: dưới
`ROS_LOCALHOST_ONLY=1`, lưu lượng SPDP **vẫn chảy hai chiều bình thường** giữa
router và node ROS. Nghẽn nằm sau đó: node ROS chỉ whitelist `127.0.0.1` và **âm
thầm loại** mọi locator của peer không nằm trên interface đó; router (Fast DDS
thuần) bind mọi interface và quảng bá cả IP LAN thật → locator SEDP/unicast của nó
bị loại → không cặp Reader/Writer nào khớp. Thêm `whitelist-interfaces: ["127.0.0.1"]`
vào **từng participant** (tag per-participant, parse ở
`ddspipe_yaml/src/cpp/YamlReader_participants.cpp`, KHÔNG phải tag top-level) là
xong: talker(0)→listener(1) qua cầu sạch dưới `ROS_LOCALHOST_ONLY=1`.

**Nút 2 — service `/b2/cmd`: không sửa được, nên bỏ khỏi đường M4.** Test lại với
`whitelist-interfaces` đã đúng VÀ `ROS_LOCALHOST_ONLY=1`, dùng service ROS 2 chuẩn
(`demo_nodes_cpp add_two_ints_server` domain 0 + `ros2 service call` domain 1) để
loại trừ yếu tố `dib_msgs`: server log `Incoming request a: 3 b: 4` (request qua
được), client treo, **không bao giờ có reply**. Lỗi RPC-bridge thật của 2.2.0,
độc lập hoàn toàn với nút 1. → Thay vì ghép domain_bridge chỉ vì một service,
**chuyển lệnh drone→box sang topic** `b2/drone_cmd` (`dib_msgs/msg/BoxCmd`).
An toàn vì reply cũ vốn vô nghĩa: `box_state_manager::box_cmd_callback()` set
`response->success = true` ngay dòng đầu rồi mới ném việc sang thread rời — comment
trong `box_link.hpp` từ M3 đã ghi rõ "telemetry là hợp đồng thật". Service `b2/cmd`
giữ nguyên cho vai trò operator/server (`agent_id % 10 == 0`), chỉ là không đi qua
ranh giới domain nữa.

**Bẫy phụ — type tuỳ biến cần khai `type` tường minh.** Cấu hình "không allowlist,
bridge mọi thứ" bắc cầu `std_msgs/String` (demo talker/listener) ngon lành nhưng
mang **0 message** cho `dib_msgs/BoxCmd` trong cùng điều kiện; test cùng-domain xác
nhận message/QoS không có vấn đề gì. Phải khai cả tên lẫn type DDS-mangled:
```yaml
allowlist:
  - name: "rt/b2/drone_cmd"
    type: "dib_msgs::msg::dds_::BoxCmd_"        # <ros_pkg>::msg::dds_::<MsgName>_
```

**Bản 3.x vẫn là ngõ cụt** — build lại 3.5.1 (Fast-DDS 3.6.1) và đo lại: talker phát
liên tục, listener nhận 0. Giống hệt 2026-07-30, khác ngày khác bản build ⇒ không
phải trùng hợp. Fast DDS 3.6 không discovery được endpoint 2.6 của Humble, và router
link Fast DDS nào là quyết định lúc build — không tham số cấu hình nào đổi được.

**Tầng-1 (node giả, KHÔNG Gazebo, dùng `dds_router_split.yaml` THẬT) — PASS 2026-08-05:**

| Luồng | Kết quả qua cầu (42↔0) |
|---|---|
| `/b2/telemetry` box→drone | ✅ drone nhận `box_state=9 box_id=2` |
| `/d1/telemetry` drone→box | ✅ box nhận `system_status=111` (giữ BEST_EFFORT/VOLATILE) |
| `/b2/drone_cmd` drone→box | ✅ 7/7 lệnh tới: `REQUEST_LANDING command=23 agent_id=12` |
| Nhân quả | ✅ tắt router → drone vẫn publish `#6`,`#7`, box **dừng nhận** sau `#5` |

**Cầu dự phòng cũng PASS cùng ngày:** `dib_split_bridge` đã sửa từ bắc cầu service
`b2/cmd` sang topic `b2/drone_cmd` cho khớp code mới; chạy lại cùng bộ script tầng-1
→ `b2/telemetry` tới drone, 6/6 `REQUEST_LANDING` tới box. Nên "dự phòng" là thật,
không phải lý thuyết.

**Ghi chú công cụ:** `ros2 topic echo/list/info` treo và ném
`xmlrpc.client.Fault: !rclpy.ok()` khi soi topic cross-domain, kể cả sau
`ros2 daemon stop` — đó là lớp daemon/XML-RPC của ros2cli, **không** phản ánh cầu
có chạy hay không. Chẩn đoán DDS-Router phải dùng subscriber `rclpy` viết tay
(không phụ thuộc daemon, đúng cách node C++ thật hoạt động).

**Tầng-2 lần 1 (Gazebo, split thật) — bắc cầu ĐÚNG nhưng vòng đời kẹt ở `SECURING_DRONE`.**
Mọi giao diện hợp đồng qua được: box log `Drone command received: 23` (REQUEST_LANDING
qua cầu) → `EMPTY→IDLE→PREPARING_FOR_LANDING→WAITING_FOR_LANDING`, `Drone telemetry
connected=1`; drone log `BoxLink: box_state 7 -> 8`; hạ cánh `aim_error=0.012m`,
`yaw_error=0.00deg`; box kẹp H/V, đóng nắp, `Powering off drone`,
`/dock/power_button/cmd command=0 -> drone power OFF`. Rồi **đứng im**: box ở
`SECURING_DRONE(8)`, drone đếm `DONE: waiting for box to charge (…s/90s, box_state=8)`
tới hết 90 s.

**Nguyên nhân — thiếu một topic trong danh sách bắc cầu, không phải lỗi cầu.**
Box rời `POWER_OFF → DONE → CHARGING` chỉ khi `d1/telemetry` im quá 5 s
(`securing_state_manager.cpp:236`). Phần cứng thật: cắt điện → máy tính drone tắt →
im miễn phí. SITL: MAVROS vẫn chạy, nên `box_hardware_adapter` publish cờ
`/dock/drone_power` và `mavros_to_dib_telemetry` NGỪNG phát khi nhận `false`. Ở
M1–M3 (một domain) cờ này đi thẳng; ở M4 nó nằm **bên domain box (42)** trong khi
`mavros_to_dib_telemetry` chạy **bên domain drone (0)** — và nó không có trong
allowlist → node phía drone không bao giờ biết đã bị cắt điện → vẫn phát telemetry →
box chờ mãi. Dấu hiệu xác nhận: **không** có dòng `Dock power OFF: stopping
publishing d1/telemetry` bên drone.

**Sửa:** thêm `/dock/drone_power` (`std_msgs/msg/Bool`, RELIABLE/**TRANSIENT_LOCAL**,
box→drone) vào cả hai cầu, đánh dấu rõ là **fixture chỉ SITL** (bỏ trên máy thật —
ở đó đường điện vật lý làm việc này). Đã kiểm riêng: cả `true` lẫn `false` qua cầu,
giữ đúng TRANSIENT_LOCAL, trên **cả** DDS-Router lẫn `dib_split_bridge`.

**Tầng-2 lần 2 (sau khi bắc cầu `/dock/drone_power`) — PASS 2026-08-05.** Vòng đời
khép trọn qua split domain:
```
box(42):   EMPTY→IDLE→PREPARING_FOR_LANDING→WAITING_FOR_LANDING→SECURING_DRONE
           sub-state 1→2→3→4→5→6→7 "Process done" → CHARGING
drone(0):  TOUCHDOWN aim_error=0.022m yaw_error=0.01deg
           BoxLink: box_state 8 -> 9 → "Box reached CHARGING — cycle complete" → DONE→IDLE
```
Mắt xích vừa sửa hoạt động đúng: drone log `Dock power OFF: stopping publishing
d1/telemetry` (trước khi sửa dòng này KHÔNG xuất hiện) → box thấy telemetry im →
`POWER_OFF → DONE → CHARGING` sau ~4.6 s.

### Chứng minh cầu thật sự mang dữ liệu (2026-08-05)

**DDS-Router 2.2.0 không log từng message** — chạy `-d` hoặc
`--log-verbosity info --log-filter ".*"` vẫn chỉ in `DDS Router running.` rồi im
(đã kiểm cả hai). Nên bằng chứng lấy từ ba nguồn khác, đều mạnh hơn một dòng log:

**(a) Socket mạng — cứng nhất.** ROS 2 ánh xạ domain sang cổng UDP theo công thức
cố định `7400 + 250 × domain`: domain 0 → 7400, domain 42 → 17900. Đo thật bằng
`ss -uapn`:

| Tiến trình | Domain | Cổng UDP |
|---|---|---|
| `box_side.py` | 42 | 17900 + multicast 239.255.0.1:17900, 17912, 17913 — **không có 7400** |
| `drone_side.py` | 0 | 7400 + multicast 239.255.0.1:7400, 7410, 7411 — **không có 17900** |
| `ddsrouter` | — | **7400 VÀ 17900**, cả unicast lẫn multicast |

Hai node ROS nghe hai cổng rời nhau nên **về mặt vật lý không thể nghe thấy nhau**;
router là tiến trình DUY NHẤT đứng chân ở cả hai domain. Mọi message qua được đều
buộc phải đi qua nó — không còn khả năng nào khác. Đây là bằng chứng loại trừ, không
phải suy luận.

**(b) Nhân quả.** Tầng-1: tắt router → drone vẫn publish `#6`,`#7`, box dừng nhận
sau `#5`. M4.1: chưa bật cầu → loop kẹt ở `WAIT_BOX_READY`/`EMPTY`.

**(c) Nội dung log ứng dụng.** Mỗi dòng là một message đã vượt ranh giới domain vì
bên phát và bên nhận ở hai domain khác nhau: `Drone command received: 23` (box@42 ←
BoxLink@0), `Drone telemetry connected=1` (box@42 ← mavros bridge@0),
`BoxLink: box_state 7 -> 8` (drone@0 ← box_state_manager@42),
`Dock power OFF: ...` (drone@0 ← box_hardware_adapter@42).

### Kiểm cuối: 8/8 chính thức + nhân quả tầng-2 (2026-08-05)

Đóng 3 việc còn treo trước khi coi M4 đóng ở cùng mức chặt M3 (chi tiết đầy
đủ + log: `docs/m4.md` Phụ lục I).

**1. Driver mới cho split-domain** —
`docs/m4_split_domain_test/m4_full_loop_monitor.py`. `m3_full_loop_monitor.py`
subscribe `/box/state` trực tiếp (không nằm trong 3 giao diện bắc cầu) nên một
tiến trình domain drone không bao giờ thấy nó trong split-domain; bản mới đọc
`box_state` từ field lồng sẵn trong `b2/telemetry` (đã bắc cầu) — tiêu chí Pass
giữ nguyên 8 mục của M3.

**2. Kịch bản chạy đủ split-domain, driver tự động — ✅ PASS 8/8.** FSM trace
khớp hoàn toàn tiêu chí nhân quả gốc (box PREPARING sau khi drone vào
WAIT_BOX_READY; drone START sau khi box WAITING_FOR_LANDING; box GPS valid
qua bridge). Giữa `START` và `FINAL_APPROACH` có 4 lần lặp
`SEARCH↔HORIZONTAL_APPROACH↔DESCEND_ABOVE_TARGET` trước khi khoá hẳn —
hành vi tracker (M3), không phải hồi quy M4.

**3. Kịch bản tắt cầu giữa chừng một chuyến bay ĐANG SỐNG (không phải M4.1
"chưa từng bật") — ✅ PASS, có log đầy đủ không cắt:**
```
217.927  FSM: PRELANDING_CHECK → WAIT_BOX_READY
217.961  WAIT_BOX_READY: box_state=0 (want 7), accepted=1, 0.0/30.0s
...      (REQUEST_LANDING publish lặp lại ~15 lần, box_state luôn = 0)
257.428  [ERROR] WAIT_BOX_READY: box b2 not ready after 30.0s (...). FALLBACK.
257.428  FSM: WAIT_BOX_READY → FALLBACK
257.461  [WARN] Fallback → reverting to AUTO.LAND (GPS landing)
257.494  TOUCHDOWN: drone=(1.6545,-1.7180) aim=(0,0) aim_error=2.385m alt_agl=0.005m
```
Box (qua driver domain drone) đứng nguyên `EMPTY(0)` suốt 39.5s liên tục —
không một bản tin `BOX -> ...` mới nào trong lúc cầu chết, dù
`REQUEST_LANDING` vẫn publish đều. Đúng 30.0s sim-time, `FALLBACK` tự kích
hoạt (không phải do người dùng ép), `set_mode("AUTO.LAND")` thật.

**Phát hiện phụ có giá trị:** `aim_error=2.385m` (fallback GPS-only, chưa
từng khoá marker) so với `aim_error=0.022m` (2.2cm) khi cầu sống — cầu chết
không chỉ treo bắt tay mà còn ép hệ thống rơi về hạ cánh kém chính xác hơn
~100 lần, đúng thiết kế an toàn của `st_fallback()`.

> Công cụ tạm dùng khi test: gate `test_hold_ok` (ép `PRELANDING_CHECK` giữ
> tối thiểu 5s) thêm tạm vào `offboard_precland_controller.cpp` để có đủ
> thời gian Ctrl+C tắt `ddsrouter` đúng lúc (cửa sổ gốc chỉ ~0.1–1s). Đã gỡ
> và build lại sạch ngay sau khi test xong — không có trong code khi bay
> thật.

**4. Hồi quy single-domain (M1–M3) sau khi đổi `BoxLink`** — người dùng đã
tự chạy và xác nhận trước đó, không lặp lại trong đợt kiểm cuối này.

### Kết quả & chứng minh — vì sao bỏ DDS-Router (2026-07-30)

> ⚠️ **Lịch sử.** Finding 3 (service reply) vẫn đúng, nhưng nó không còn chặn M4
> vì service đã ra khỏi đường bắc cầu (xem mục 2026-08-05 ở trên). Nhận định
> "2.2 cần `ROS_LOCALHOST_ONLY=0`" đã được thay bằng `whitelist-interfaces`.

### Kết quả & chứng minh — vì sao bỏ DDS-Router (2026-07-30)

Test theo **2 tầng**: tầng-1 pub/sub giả nhẹ qua 2 domain (KHÔNG Gazebo) để kiểm
"cầu có thông không"; tầng-2 (Gazebo, M4.4) chỉ chạy một lần cuối. Toàn bộ kết
luận dưới đây rút từ tầng-1.

**Phiên bản Fast DDS (gốc rễ mọi chuyện):**

| Thành phần | Fast DDS |
|---|---|
| ROS 2 Humble (`rmw_fastrtps`) | **2.6.11** (`libfastrtps.so.2.6`) |
| DDS-Router 3.5.1 (build đầu) | **3.6.1** (`libfastdds.so.3.6`) |
| DDS-Router 2.2.0 (build sau) | **2.14.0** (`libfastrtps.so.2.14`) |

**Finding 1 — DDS-Router 3.x KHÔNG hợp Humble (lệch Fast DDS 2.6 vs 3.x).**
Kiểm `.repos` từng tag: `v3.0.0→3.0.1`, `v3.4.0→3.4.1`, `v3.5.1→3.6.1` — **cả dòng
3.x đều Fast DDS 3.x**, nên "hạ xuống 3.4" vô ích. Chứng minh dứt điểm: build
`hello_world` Fast DDS **3.6**, dùng XML profile tách domain 0/1, cho router 3.6
bắc cầu — subscriber 3.6 (domain 1) **nhận** publisher 3.6 (domain 0) ✅; nhưng
cùng router đó bridge **talker/listener ROS-2.6 kinh điển = KHÔNG gì qua** (thử cả
`ROS_LOCALHOST_ONLY` 0 và 1). Khác biệt duy nhất = 2.6 vs 3.6 ⇒ participant Fast
DDS 3.6 không discovery được endpoint 2.6. (Team báo "3.4 OK" gần như chắc chắn
chạy trên distro Fast DDS 3.x — Jazzy/Rolling — không phải Humble.)

**Finding 2 — DDS-Router 2.2.0 (Fast DDS 2.14) bridge TOPIC hoàn hảo → M4.2 PASS.**
Talker(0)→listener(42) qua router 2.2 nhận được; `/d1/telemetry`
(`system_status=111`) chảy 0→42 và `/b2/telemetry` (`box_state=9`) chảy 42→0 —
**cả hai chiều PASS**, đúng type `dib_msgs` thật, giữ BEST_EFFORT cho d1.
- **Điểm phải nhớ:** DDS-Router là Fast DDS **thuần**, KHÔNG đọc `ROS_LOCALHOST_ONLY`
  (đó là cơ chế của rmw). Với `=1`, node ROS bó loopback còn router mở mọi
  interface → không khớp discovery, cầu tắc. **Phải chạy mọi thứ với
  `ROS_LOCALHOST_ONLY=0`** (đơn máy nên vẫn an toàn). Sửa lại so với plan cũ (=1).
- Schema config 2.2.0: bắt buộc `version: v4.0` (từ chối `v3.1` cũ), QoS dạng
  **boolean** (`reliability: false` = BEST_EFFORT).

**Finding 3 — DDS-Router 2.2.0 KHÔNG route REPLY của service `/b2/cmd` → M4.3 tắc.**
Dựng server `BoxCmd` giả trên domain 42, client trên domain 0, router ở giữa:
- **Request 0→42: luôn tới server** (server xử lý đủ 6/6 request).
- **Reply 42→0: KHÔNG bao giờ về client.** Thử vét cạn: `ros2 service call`
  transient, client rclpy bền chờ 20s, 6 request liên tiếp cách nhau, có và không
  allowlist `rq/rr` — **mọi trường hợp reply đều mất**, router không in warning.
- `RpcBridge` của 2.2.0 CÓ code correlation `SampleIdentity` (ServiceRegistry) nhưng
  vẫn fail — nhiều khả năng rmw_fastrtps 2.6 và Fast DDS 2.14 xử lý
  `related_sample_identity` khác nhau. Đây là **bẫy số 1** của plan gốc, nhưng hóa
  ra không phải do quên allowlist mà do bản thân RPC bridge không hoạt động.

**Quyết định:** contract có **đúng 1 service** (`/b2/cmd`) và mọi thứ khác là topic.
Ràng buộc: **giữ nguyên code box/telemetry**. → Chuyển sang **`domain_bridge`**
(`ros-humble-domain-bridge`) — công cụ ROS-native bắc cầu ROS_DOMAIN_ID, tạo proxy
client/server service THẬT qua rmw nên xử lý reply đúng, và bridge topic bình
thường. Một công cụ cho cả topic lẫn service, **không sửa một dòng code nào**.
Topology / hướng domain / tiêu chí Pass (M4.1→M4.4) giữ nguyên; chỉ thay "động cơ".

### Nghiệm thu `domain_bridge` — chạy split THẬT (2026-08-03)

> ⚠️ **Lịch sử.** Kết quả này vẫn đúng nhưng `domain_bridge` giờ là **phương án
> dự phòng**; `dib_split_bridge` đã đổi từ bắc cầu service `b2/cmd` sang topic
> `b2/drone_cmd` cho khớp code hiện tại, nên các dòng "service b2/cmd" dưới đây
> mô tả bản cũ của node cầu.

Node cầu: `dib_domain_bridge/dib_split_bridge 42 0` (một node C++, domain_bridge
API, mang đúng 3 giao diện hợp đồng). Chạy với box `ROS_DOMAIN_ID=42`, drone `=0`,
`ROS_LOCALHOST_ONLY=1`, cầu chạy tiến trình riêng (domain lấy từ args). Cầu in:
`bridging b2/telemetry(42->0) d1/telemetry(0->42) service b2/cmd(server@42,client@0)`.

**Tầng-1 (node giả `dib_msgs` thật, KHÔNG Gazebo) — PASS 4/4:**

| Luồng | Kết quả qua cầu (42↔0) |
|---|---|
| `/b2/telemetry` box→drone | ✅ drone nhận `box_state=9 box_id=2` |
| `/d1/telemetry` drone→box | ✅ box nhận `system_status=111` (giữ BEST_EFFORT/VOLATILE) |
| `/b2/cmd` request | ✅ box nhận `command=1 agent_id=12` |
| `/b2/cmd` **reply** | ✅ drone nhận `success=True` — điều DDS-Router 2.2 KHÔNG làm được (Finding 3) |

Script tầng-1: `docs/m4_split_domain_test/tier1/{box_side,drone_side}.py` (+ README).

**Tầng-2 (Gazebo, split thật, box-side `dib_bringup ... include_telemetry_bridge:=false`):**
box đi trọn `EMPTY→IDLE→PREPARING_FOR_LANDING→WAITING_FOR_LANDING→SECURING_DRONE`,
log `Drone telemetry connected=1` + nhận chuỗi lệnh box (1/23/4) → đóng clamp →
power off drone. `/b2/telemetry`, `/d1/telemetry`, `/b2/cmd` đều đọc/gọi được đúng
qua ranh giới domain. ✅

**Kết luận M4:** đạt trên `domain_bridge`, **không sửa một dòng code hợp đồng nào**.
Bằng chứng nhân quả mạnh nhất (tùy chọn, chưa chạy): tắt cầu giữa chừng → loop phải
đứng ở `WAIT_BOX_READY`/`EMPTY`. Tầng-1 có thể chứng minh nhanh cùng ý (bật A+B
chưa bật cầu = drone im, bật cầu = drone thấy `ARRIVED`).

*Plan grounded ban đầu (giữ làm tham chiếu — topology không đổi):*

### Mục tiêu

Trên phần cứng thật, máy tính đồng hành của drone và máy tính của box là **hai
máy riêng, hai mạng riêng**. Chạy chung một `ROS_DOMAIN_ID` nghĩa là mọi node
hai bên discovery lẫn nhau — bão discovery, ghép cặp nhầm, phụ thuộc chéo. M4
tách làm **hai domain** và **chỉ bắc cầu đúng hợp đồng** box↔drone qua eProsima
DDS-Router.

### Bề mặt cầu — CHỈ 3 giao tiếp (đọc từ code, không đoán)

| Hướng | Tên (id mặc định) | Kiểu | QoS | Nguồn |
|---|---|---|---|---|
| drone → box | `/b<box_id>/cmd` → `/b2/cmd` | **service** `dib_msgs/srv/BoxCmd` | default | `box_link.cpp:11`; `box_state_manager` create_service |
| box → drone | `/b<box_id>/telemetry` → `/b2/telemetry` | topic `dib_msgs/msg/BoxTelemetry` | default | `offboard_precland_controller.cpp:246` |
| drone → box | `/d<drone_id>/telemetry` → `/d1/telemetry` | topic `dib_msgs/msg/DroneTelemetry` | **BEST_EFFORT · VOLATILE · KEEP_LAST 1** | `mavros_to_dib_telemetry_node.cpp:35-38`; `box_state_manager.cpp:627` |

Mọi thứ khác **cục bộ một bên, KHÔNG bắc cầu**: bên drone/sim có MAVROS + PX4 +
tracker + gz bridges + ros2_control (khớp gimbal); bên box có `/gps` +
`/lid|clamp|dock/*` + ros2_control (khớp box). Trên phần cứng thật `/gps` do GPS
của box tự publish nội bộ nên **không** qua cầu.

> **Bẫy số 1 — service qua DDS-Router.** DDS-Router bắc cầu **topic**. Một ROS 2
> service = 2 topic ẩn `rq/<service>Request` + `rr/<service>Reply` (cộng hậu tố
> theo RMW). Allowlist phải liệt kê **cả hai topic ẩn đó**, không phải tên service
> trần — nếu quên, `REQUEST_LANDING`/`TURN_OFF_DRONE` không bao giờ tới và loop
> đứng ở `WAIT_BOX_READY` mà không báo lỗi. Client và server nên cùng RMW để
> định danh service khớp.
>
> **Bẫy số 2 — QoS phải khớp.** `/d<id>/telemetry` là **BEST_EFFORT**; participant
> DDS-Router phải giữ đúng reliability, nếu ép RELIABLE thì hoặc rớt mẫu hoặc chặn.
>
> **Bẫy số 3 — `use_sim_time` không qua cầu.** Trong SITL bên drone chạy sim time,
> nhưng đây là chuyện của mỗi domain; DDS-Router chuyển dữ liệu topic, không chuyển
> `/clock`. Nếu muốn hai bên cùng đồng hồ trong SITL thì phải bắc cầu `/clock`
> **có chủ đích** — mặc định thì đừng, để mỗi bên tự chủ như phần cứng thật.

### Thiết kế

- Bên box: `ROS_DOMAIN_ID=<B>` (ví dụ 42). Bên drone/sim: `ROS_DOMAIN_ID=<D>`
  (ví dụ 0).
- Một tiến trình `dds-router` với **hai participant `local`** (một cho domain D,
  một cho domain B) và **một `allowlist`** đúng 5 topic: `b2/telemetry`,
  `d1/telemetry`, và 2 topic ẩn của service `b2/cmd` (`rq/.../b2/cmdRequest`,
  `rr/.../b2/cmdReply`).
- Config YAML để trong repo: `ros2_ws/.../config/dds_router_split.yaml` (bản
  thực thi sẽ chốt tên topic ẩn bằng `ros2 topic list -t` khi hai domain đang chạy).

### Cách test (dự kiến) — lặp lại M3c qua cầu

1. **Chứng minh cô lập TRƯỚC khi bật router:** bên box `ros2 topic list` **không**
   thấy `/mavros/*`; bên drone **không** thấy `/lid/status`. Thấy ⇒ chưa thật sự
   tách domain (kiểm `ROS_DOMAIN_ID` từng terminal).
2. **Bật `dds-router`**, chạy lại đúng kịch bản M3c → vẫn tới `CHARGING(9)`,
   monitor **8/8**, sai số hạ cánh vẫn ~cm.
3. **Tiêu chí Pass mang tính nhân quả:** loop khép QUA router; và khi **TẮT
   router** giữa chừng, loop đứng ở `WAIT_BOX_READY` (drone) / `EMPTY` (box) vì
   `REQUEST_LANDING` không qua được — chứng minh chính router mang lệnh, không
   phải domain rò rỉ. Cùng triết lý "observer thụ động" của M3.

### Ngoài phạm vi M4

- Đa drone / đa box (`agent_id = drone_id*10 + 2` đã hỗ trợ nhưng chưa test).
- Bảo mật DDS (SROS2) → M5.
- Hai domain trên **hai máy vật lý**: M4 làm trên một host trước (hai domain cùng
  máy); tách máy thật thuộc M5 hardening.

---

## M5 — Hardening + đóng gói

*Chưa bắt đầu.*
