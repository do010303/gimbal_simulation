# PX4 Gimbal Precision Landing

Pipeline hạ cánh chính xác cho drone `x500_gimbal` trong Gazebo SITL bằng
**Fractal ArUco** (tracker C++ `aruco_fractal_tracker`, marker fractal lồng nhau
cạnh ngoài 50 cm) qua **MAVROS**. Mốc hiện tại: **M3 — drone-in-a-box khép trọn
vòng đời tới `CHARGING`** (mục 2). Chi tiết thiết kế M3: `docs/m3.md`.

Đây là mục lục chạy-được. Mọi giải thích *tại sao* (bẫy đã gặp, lý do một dòng
lệnh phải đứng ở đúng chỗ đó) nằm ở **[Phụ lục](#phụ-lục--ghi-chú--bẫy-kỹ-thuật)**
cuối file — đọc khi có gì đó không chạy, không cần đọc trước.

---

## 1. Cài đặt — từ máy trống tới build xong

```bash
# 1. Build gz_ros2_control TỪ NGUỒN cho Harmonic (bắt buộc, một lần — xem Phụ lục A.1)
sudo apt remove -y ros-humble-gz-ros2-control      # bản apt là cho Fortress, gây segfault
mkdir -p ~/gz_ros2_control_ws/src && cd ~/gz_ros2_control_ws/src
git clone -b humble https://github.com/ros-controls/gz_ros2_control.git
cd ~/gz_ros2_control_ws
export GZ_VERSION=harmonic                          # PHẢI export trước rosdep/build
rosdep install -r --from-paths src -i -y --rosdistro humble
colcon build --symlink-install

# 2. Clone repo vào cây PX4
cd ~/PX4/examples
git clone <repo-url> SITL_PrecisionLanding
cd SITL_PrecisionLanding

# 3. Đồng bộ world/model/texture sang cây PX4 (gz server của PX4 load từ đây)
cd ~/PX4 && rsync -a examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/ Tools/simulation/gz/
cd examples/SITL_PrecisionLanding

# 4. Verify: cài dep + build libaruco + giải nén mesh box + kiểm gz_ros2_control
source /opt/ros/humble/setup.bash
chmod +x verify_build_env.sh && ./verify_build_env.sh     # dừng và sửa nếu báo FAIL/WARN

# 5. Build
cd ros2_ws && colcon build --symlink-install && source install/setup.bash && cd ..

# 6. Dọn tiến trình cũ TRƯỚC mỗi lần chạy (thói quen, không chỉ lần đầu)
./scripts/stop_pipeline.sh      # phải in ra: sach
```

`box_manager`, `box_simulation`, `dib_msgs`, `precision_landing` đã nằm trong
repo — không phải clone thêm gì khác. Bước 1 chỉ cần làm lại nếu máy chưa từng
build `gz_ros2_control` cho Harmonic.

Xong bước 5 là build được. Chạy pipeline: **mục 2** (drone-in-a-box, khuyến
nghị) hoặc **mục 3** (hạ cánh đơn, không có box).

**Không dùng `verify_build_env.sh`?** Cài tay + build `libaruco`: Phụ lục A.4.
Kiểm tài nguyên đã sync đúng (FOV, mesh): Phụ lục A.2. Sự cố ArUco: Phụ lục A.4.

---

## 2. Drone-in-a-Box — Pipeline Đầy Đủ (M3)

> **Mốc M3 — ✅ PASS 8/8 (2026-07-29), sai số hạ cánh thật 4.9 cm.** Chi tiết
> đầy đủ (thiết kế bắt tay, hợp nhất world, khép vòng đời, nhật ký bẫy, tiêu
> chí từng bước): `docs/m3.md`. File test: `docs/m3_box_handshake_test/`.

```
box_manager  ──service──▶  box_hardware_adapter  ──JointTrajectory──▶  ros2_control
     ▲                                                                      │
     └──────────────  /joint_states  ◀──────────  Gazebo (cùng world)  ◀─────┘
                                                        │
drone: MAVROS ──▶ mavros_to_dib_telemetry ──▶ box_manager
       camera ──▶ aruco_fractal_tracker ──▶ offboard_precland_controller ──▶ MAVROS
```

| Package | Vai trò |
|---|---|
| `precision_landing` | Tracker fractal + `offboard_precland_controller` (FSM hạ cánh, C++) + `mavros_to_dib_telemetry` |
| `box_manager` | FSM box (`EMPTY → PREPARING_FOR_LANDING → WAITING_FOR_LANDING → SECURING_DRONE → CHARGING`) |
| `box_hardware_adapter` | Dịch service `box_manager` ↔ `JointTrajectory` cho ros2_control; `/joint_states` → `/lid/status`, `/clamp/status` |
| `box_simulation` | Model box khớp động (nắp, 2 cặp kẹp) |
| `dib_box_marker` | Marker fractal 0.50 m trên sàn box |

### Header cho MỌI terminal
```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

### 2.1. Giai đoạn A — dựng world, kiểm box/marker (2 terminal)

Chạy riêng trước phần còn lại: nếu marker không hiện thì cả pipeline chắc chắn
thất bại, và giai đoạn này chỉ tốn 2 tiến trình thay vì 7.

```bash
# T1 — PX4 + Gazebo
export GZ_SIM_RESOURCE_PATH=$HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share
cd ~/PX4 && PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing
# đợi tới pxh> rồi mới sang T2. Không màn hình: thêm HEADLESS=1 (xem Phụ lục A.5)
```

```bash
# T2 — spawn box + marker vào chính world đó (chờ ~40s cho 4 controller nạp xong)
ros2 launch box_simulation box_spawn_only.launch.py
```

```bash
# Kiểm (sau T2 ~40 giây)
gz model --list                       # có Box và dib_box_marker
ros2 control list_controllers         # 4 dòng, tất cả 'active'
ros2 topic echo --once /joint_states  # 6 joint
```
Controller còn `unconfigured`: đã nạp, chỉ chưa qua nốt bước cuối do timeout —
hoàn tất bằng tay (xem Phụ lục A.5 nếu cần hiểu vì sao):
```bash
ros2 control set_controller_state joint_state_broadcaster configure
ros2 control set_controller_state joint_state_broadcaster active
```

```bash
# Mở nắp và xác nhận marker (PHẢI -r -t, không --once — xem Phụ lục A.5)
ros2 topic pub -r 2 -t 6 /joint_lid_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["lid_left_joint"], points: [{positions: [1.57], time_from_start: {sec: 2}}]}'
```
Nhìn vào lòng box: phải thấy ô marker fractal đen-trắng trên mặt sàn.

### 2.2. Giai đoạn B — vòng kín (thêm 5 terminal)

Giữ nguyên T1, T2.

| T | Lệnh | Vai trò |
|---|---|---|
| 3 | `ros2 launch precision_landing sitl_precland.launch.py` | bridge + tracker + controller |
| 4 | `ros2 launch precision_landing sitl_mavros.launch.py` | MAVROS (đồng hồ mô phỏng — bắt buộc launch này, xem Phụ lục A.6) |
| 5 | `ros2 launch precision_landing dib_bringup.launch.py` | cả 3 node phía box |
| 6 | `ros2 launch $PWD/docs/m3_box_handshake_test/sitl_fixtures.launch.py` | fixture GPS, **chỉ SITL** |
| 7 | `ros2 run rqt_image_view rqt_image_view /landing/annotated_image` | HUD giám sát — mở suốt lượt chạy |

**Kiểm 3 thứ trước khi bay** (10 giây bây giờ, tránh mất cả lượt bay):
```bash
ros2 param get /mavros/mavros_node use_sim_time             # True
ros2 control list_controllers                               # 4 dòng 'active'
ros2 topic echo --once /mavros/state                        # connected: true
```

Chấm điểm tự động cả lượt bay (tuỳ chọn, thêm một terminal):
```bash
python3 docs/m3_box_handshake_test/m3_full_loop_monitor.py   # 8 tiêu chí M3
```

**Bay**, trong `pxh>` của Terminal 1:
```
pxh> param set NAV_DLL_ACT 0      # bắt buộc nếu không mở QGroundControl — Phụ lục A.6
pxh> commander takeoff
pxh> commander land
```

FSM đứng ở `IDLE` khi chưa bay là **đúng**. Sau bay, `WAIT_BOX_READY → START →
HORIZONTAL_APPROACH → DESCEND_ABOVE_TARGET → FINAL_APPROACH`, chạm đất, rồi
**còn ~35–40 giây nữa** box mới kẹp xong / đóng nắp / sang `CHARGING` — đừng
Ctrl+C sớm. Một lượt đạt = FSM hai bên đan xen đúng nhân quả và kết thúc ở
`CHARGING`:
```
DRONE  -> GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY
BOX    -> PREPARING_FOR_LANDING(6) -> WAITING_FOR_LANDING(7)
DRONE  -> START -> HORIZONTAL_APPROACH -> DESCEND_ABOVE_TARGET -> FINAL_APPROACH
MAVROS -> landed_state=ON_GROUND
BOX    -> SECURING_DRONE(8) -> CHARGING(9)
```

> **Đọc log và chẩn đoán khi có gì lệch:** dòng log trông như lỗi nhưng không
> phải, cách đọc HUD, latency vs lệch đồng hồ, cách đọc sai số hạ cánh — tất cả
> ở **`ros2_ws/src/precision_landing/README.md`**.

### 2.3. Ba cấu hình sai là hỏng cả lần chạy

1. **`box_id` phải khớp** giữa `box_state_manager.yaml` và
   `offboard_precland_params.yaml`. Lệch → FSM bỏ qua toàn bộ bắt tay, không
   báo lỗi. Xác nhận bằng log: `Derived box_telemetry_topic='/b2/telemetry'
   from box_id=2`.
2. **Box phải có toạ độ GPS** (topic `gps`, `sensor_msgs/NavSatFix`). SITL
   không ai publish thật → phải chạy fixture (T6). Thiếu thì `lat/lon=0`, drone
   bay mất hàng nghìn km.
3. **`marker_size` phải khớp plane thật.** Marker đen chiếm 80.12% cạnh ảnh
   (viền trắng 1 module) → plane = `marker_size / 0.8012`. Lệch → sai thang đo
   pose → sai độ cao → flare sớm hoặc cắm xuống.

### 2.4. Chỉnh hướng đậu của drone (`marker_yaw`)

```bash
# chỉ khởi động lại T2, không phải PX4
ros2 launch box_simulation box_spawn_only.launch.py marker_yaw:=1.5708
```
Thử `0.0` / `1.5708` / `3.1416` / `-1.5708`, giữ giá trị nào đậu drone thẳng
hàng giữa hai cặp kẹp (world Y 0.774 m, world X 0.782 m) — tiêu chí là hai cặp
kẹp, không phải màu nắp.

### 2.5. Chạy tách domain box↔drone (M4, tuỳ chọn — đang phát triển)

Trên phần cứng thật, box và drone là hai máy riêng. M4 mô phỏng điều đó trên
một host bằng hai `ROS_DOMAIN_ID`, bắc cầu 3 giao diện hợp đồng
(`/b2/telemetry`, `/d1/telemetry`, service `/b2/cmd`) qua `domain_bridge`
(ROS-native — không dùng DDS-Router, xem Phụ lục A.9). Mục 2 (một domain) vẫn
là cách chạy mặc định. **Package cầu (`dib_domain_bridge`) chưa vào repo** —
mục này ghi lại cách chạy khi nó sẵn sàng; hỏi trước khi dựa vào nó.

---

## 3. Precision Landing — hạ cánh KHÔNG có box

Cùng một binary C++ với mục 2. `offboard_precland_controller` tự nhận biết:
không có telemetry box thì bỏ qua toàn bộ nhánh bắt tay, hạ cánh thị giác
tiêu chuẩn. Không cờ nào phải bật. Khác mục 2 ở chỗ không chạy phía box, nên 4
terminal thay vì 7:

```bash
# Dọn tiến trình cũ trước (mục 1)

# T1 — PX4 SITL
cd ~/PX4 && PX4_GZ_WORLD=fractal_aruco_landing PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal

# T2 — MAVROS (chạy một lần, GIỮ NGUYÊN — đừng restart giữa chuyến bay)
source /opt/ros/humble/setup.bash
ros2 launch precision_landing sitl_mavros.launch.py
#   kiểm: ros2 topic echo --once /mavros/state   ->   connected: true

# T3 — bridge camera + tracker + controller
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch precision_landing sitl_precland.launch.py

# T4 — HUD giám sát (mở suốt lượt chạy, cùng topic với mục 2)
ros2 run rqt_image_view rqt_image_view /landing/annotated_image
```
HUD giống hệt mục 2, chỉ khác dòng `BOX:` hiện `no telemetry` — đúng và bình
thường khi không chạy phía box.

**Bay** — giống mục 2, trong `pxh>` của T1:
```
pxh> param set NAV_DLL_ACT 0      # hoặc mở QGroundControl
pxh> commander takeoff
pxh> commander land
```

Marker ở đây là `dib_box_landing_pad` tĩnh trong world (không phải box khớp
động của mục 2) — không chạy `box_spawn_only.launch.py`. Camera 1280×720 @30
Hz, hFOV 1.4137 rad (81°); control loop 30 Hz (nghiệm thu ≥20 Hz). Ba tầng
fractal 50 / 12.5 / 3.125 cm. Nếu PX4 không ở `~/PX4`, truyền
`marker_configuration:=/abs/path/custom_fractal.yml`. Controller dùng ENU
(`search_x=East`, `search_y=North`).

### 3.1. Để PX4 tự hạ cánh thay vì offboard

Hai kiến trúc khác nhau cho cùng một việc, dùng chung tracker C++:

| | Ai điều khiển | T3 launch |
|---|---|---|
| **Offboard** (mặc định) | `offboard_precland_controller` bơm setpoint qua MAVROS | `sitl_precland.launch.py` |
| **PX4 native** | `landing_target_bridge` đẩy `LandingTarget` (LOCAL_NED), PX4 tự hạ | `sitl_px4_precland.launch.py` |

```bash
# T3 thay bằng:
ros2 launch precision_landing sitl_px4_precland.launch.py
```
Hữu ích khi cần đối chiếu chất lượng hạ cánh của PX4 với nhánh offboard, hoặc
khi không được phép dùng OFFBOARD.

### 3.2. Bài bay tự động qua service

```bash
# T5
source ~/test_req/install/setup.bash
ros2 launch ros2_telemetry plan_upload.launch.py drone_id:=d1
# T6
ros2 service call /d1/mission_upload dib_msgs/srv/MissionUpload "{mission: [
  {command: 22, param1: 0.0, param2: 0.0, latitude: 47.397929,  longitude: 8.546217, altitude: 15.0},
  {command: 16, param1: 5.0, param2: 0.0, latitude: 47.39797,   longitude: 8.546322, altitude: 15.0},
  {command: 16, param1: 5.0, param2: 0.0, latitude: 47.3979298, longitude: 8.546217, altitude: 15.0},
  {command: 23, param1: 0.0, param2: 0.0, latitude: 47.3979298, longitude: 8.546217, altitude: 0.0}
]}"
```

### 3.3. Camera thật (RTSP, không cần PX4)

Kiểm nhận diện của camera vật lý (SIYI A8 Mini / camera IP) mà chưa cần SITL/FCU:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch precision_landing real_fractal_detect.launch.py enable_mavros:=false
ros2 run rqt_image_view rqt_image_view      # topic /siyi/fractal_debug
ros2 topic echo /siyi/fractal_pose          # luồng pose
```
Đổi RTSP/calibration ở `ros2_ws/src/precision_landing/config/rtsp_publisher_params.yaml`.

`siyi_camera_bridge` truyền tham số thẳng trên dòng lệnh thay vì qua file —
tiện khi đang dò tham số ngoài hiện trường:
```bash
ros2 launch siyi_camera_bridge real_fractal_detect.launch.py enable_mavros:=false \
  rtsp_url:=rtsp://192.168.168.16:8554/main.264 marker_size:=0.162 flip_180:=false \
  marker_configuration:=$PWD/px4/Tools/simulation/gz/models/fractal_aruco_marker/custom_fractal.yml
```
Hai launch chạy cùng một node C++ (`precision_landing/rtsp_publisher`), chỉ
khác cách nạp tham số — số đo so sánh được với nhau. Quy trình đo thực địa đầy
đủ (đo xa, ghi CSV, lỗi hay gặp): `ros2_ws/src/siyi_camera_bridge/README.md`.

---

## 4. Tài liệu khác

- **Chẩn đoán, đọc log, đọc HUD:** `ros2_ws/src/precision_landing/README.md`.
  Phía box: `ros2_ws/src/box_manager/README.md`,
  `ros2_ws/src/box_hardware_adapter/README.md`.
- M3 đầy đủ (thiết kế, bẫy, tiêu chí nghiệm thu): `docs/m3.md`.
- Sơ đồ FSM và kiến trúc: `docs/diagrams/` — `fractal_aruco_fsm.png` (FSM hạ
  cánh), `dib_diagram.png` (kiến trúc drone-in-a-box), kèm bản nguồn `.mmd`/`.dot`.
- Marker chính thống nhất về `0.50 m` (`marker_size:=0.50`); đổi kích thước
  trong `model.sdf` thì phải đổi `marker_size` tương ứng.
- Đang giữ OFFBOARD / giữa chuyến bay: **không restart MAVROS** — giữ terminal
  MAVROS riêng, chỉ restart terminal tracker. Restart MAVROS lúc đó có thể gây
  `Critical: Connection to mission computer lost`.

---

## Phụ lục — Ghi chú & bẫy kỹ thuật

Không cần đọc trước. Mỗi mục được trỏ tới từ chỗ liên quan ở trên; vào thẳng
mục cần khi có gì đó không như ý.

### A.1. Vì sao `gz_ros2_control` phải build từ nguồn cho Harmonic

Bản apt `ros-humble-gz-ros2-control` là cho **Fortress**. Để nguyên thì gz
server **segfault ngay khi spawn box**: plugin *system* (Harmonic) nạp plugin
*hardware* qua pluginlib và vớ phải bản Fortress —
`v8::EntityComponentManager` truyền vào hàm nhận `v6::`. Chi tiết ở "Bẫy P1.4"
trong `docs/m3.md`.

`GZ_VERSION` quyết định build cho Harmonic hay Fortress — CMakeLists đọc
`$ENV{GZ_VERSION}`: `harmonic` → gz-sim8, mặc định → Fortress. Phải export
**trước** `rosdep`/`colcon build`.

Kiểm — cả hai `.so` phải cùng là bản Harmonic vừa build:
```bash
ls ~/gz_ros2_control_ws/install/gz_ros2_control/lib/libgz_ros2_control-system.so \
   ~/gz_ros2_control_ws/install/gz_ros2_control/lib/libgz_hardware_plugins.so
dpkg -l ros-humble-gz-ros2-control 2>/dev/null | grep '^ii' && echo "!! bản apt Fortress VẪN CÒN"
```

> **Không gỡ bản apt thì vẫn chạy được** nếu terminal chạy `make px4_sitl` đã
> source ws Harmonic trước — nhưng chỉ cần một terminal quên source là segfault
> quay lại. Gỡ hẳn thì hết đường nạp nhầm.

### A.2. Tài nguyên world/model đã sync đúng chưa

```bash
ls ~/PX4/Tools/simulation/gz/worlds/fractal_aruco_landing.sdf
ls ~/PX4/Tools/simulation/gz/models/{fractal_aruco_marker,dib_box_marker}/model.sdf
grep horizontal_fov ~/PX4/Tools/simulation/gz/models/gimbal/model.sdf   # phải là 1.4137
```

**Camera gimbal phải có `horizontal_fov` = 1.4137 rad (81°), 1280×720.** Bản
upstream của submodule `Tools/simulation/gz` để `2.0` rad (114.6°) — bước
rsync ghi đè lại đúng giá trị. Sai FOV thì marker chiếm ít pixel hơn ~1.8 lần ở
cùng khoảng cách: tracker vẫn chạy (lấy nội tham số từ `camera_info` nên vẫn
tự nhất quán), nhưng các ngưỡng approach/descend đã tinh chỉnh trong
`offboard_precland_params.yaml` **không còn là cấu hình đã đo ra PASS 8/8**.
Đây cũng là FOV mà `aruco_fractal_tracker` ghi cứng làm giá trị dự phòng
(`fx = fy = 749.338`).

World `fractal_aruco_landing.sdf` **không còn** `<include> dib_box_landing_pad`:
marker giờ nằm trên box khớp động, spawn bằng `box_spawn_only.launch.py`. Để
cả hai sẽ có hai marker giống hệt → tracker bám nhầm, drone hạ xuống pad tĩnh
(log/FSM vẫn *trông như* đúng). Cách khôi phục pad tĩnh nằm trong chú thích
file world.

**Mesh thân box ship nén.** `BOX PAD1.0_simple.dae` (visual, 270 MB) vượt giới
hạn 100 MB/file của GitHub nên repo chỉ chứa `.dae.gz` (64 MB);
`verify_build_env.sh` tự gunzip trước build. Box **vô hình** sau build ⇒ chưa
gunzip, chạy lại verify. (Mesh nắp/kẹp nhỏ nằm thẳng trong repo; `base_link_1.dae`
bỏ vì không dùng. `box_manager`/`box_simulation` được vendor thẳng vào
`ros2_ws/src/`.)

### A.3. Dọn tiến trình — bẫy `pkill` và vì sao dừng cả `ros2 daemon`

```bash
./scripts/stop_pipeline.sh      # phải in ra: sach
```
Script in số tiến trình đã dừng, SIGKILL những con lì (gz sim hay lì), dừng
luôn `ros2 daemon`, rồi kiểm lại và chỉ in `sach` khi thật sự không còn gì.

> **ĐỪNG gõ thẳng `pkill -f 'px4|gz sim|...'` — lệnh đó tự sát.** `pkill -f` so
> khớp với **toàn bộ dòng lệnh** của mọi tiến trình, kể cả dòng lệnh của chính
> cái shell vừa gõ nó, vì dòng đó có chứa chuỗi `px4|gz sim|...`. Shell chết
> ngay ở `pkill` đầu tiên, lệnh `pkill` thứ hai **không bao giờ chạy**, và:
> ```
> Đo thật: gõ pkill -> terminal im -> tưởng đã dọn xong
>          nhưng px4 + gz sim + 16 node khác vẫn sống, ăn ~5 GB và đẩy 3 GB xuống swap
> ```
> Đây là lý do "đã tắt hết rồi mà vẫn ngốn RAM". Script trên đặt chuỗi pattern
> trong **biến** (không nằm trên dòng lệnh) và loại trừ tường minh chính nó cùng
> mọi tiến trình cha.

Bỏ qua bước dọn là nguyên nhân phổ biến nhất khiến máy lag và lần chạy sau
hỏng theo kiểu khó hiểu (giữ UDP endpoint / quyền điều khiển gimbal từ phiên
trước).

> **Vì sao script dừng cả `ros2 daemon`.** Daemon cache thông tin discovery
> giữa các phiên và các `ROS_DOMAIN_ID`. Daemon cũ còn sống thì `ros2 node
> list` / `ros2 topic list` / `ros2 topic echo` **im lặng trả về rỗng** dù node
> đang chạy ngon — đúng những lệnh mà bước kiểm tiền bay dựa vào, nên rất dễ
> kết luận nhầm là pipeline hỏng. Nghi ngờ thì thêm `--no-daemon` vào lệnh
> `ros2` để hỏi thẳng, bỏ qua cache.

### A.4. Cài gói thủ công + sự cố `libaruco`

```bash
sudo apt update && sudo apt install -y \
  ros-humble-mavros ros-humble-mavros-extras ros-humble-cv-bridge \
  ros-humble-image-transport ros-humble-rqt-image-view \
  python3-colcon-common-extensions python3-opencv
# Gazebo bridge — CHỌN theo phiên bản đang cài:
#   Harmonic: ros-humble-ros-gzharmonic-bridge  ros-humble-ros-gzharmonic-image
#   Garden  : ros-humble-ros-gz-bridge          ros-humble-ros-gz-image
pip3 install -r requirements.txt
```
`libaruco` vẫn phải build từ `aruco_build/aruco.zip` (verify script làm sẵn).

Thư viện fractal là **ArUco C++ 3.1.12** (KHÔNG phải `opencv-contrib-python`),
build vào `$HOME/.local`.

| Triệu chứng | Cách sửa |
|---|---|
| `colcon` báo `Could not find a package configuration file provided by "aruco"` | Chưa build libaruco → chạy lại `./verify_build_env.sh` (unzip + cmake + `make install` vào `$HOME/.local`). |
| Runtime `error while loading shared libraries: libaruco.so.3.1` | `export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH` (nên thêm vào `~/.bashrc`). |
| verify báo thiếu `aruco_build/aruco.zip` | File 1.6 MB này phải có trong clone — kiểm `.gitignore`. |
| CMake vớ phải libaruco cũ ở `/usr/local` gây version lệch | Gỡ bản cũ, hoặc build với `CMAKE_PREFIX_PATH=$HOME/.local`. |

Kiểm: `find $HOME/.local /usr/local/lib -name 'libaruco.so*'`. Rebuild riêng
tracker:
```bash
cd ros2_ws && colcon build --symlink-install --packages-select precision_landing --cmake-clean-cache
```

> **OpenCV 4.7+:** `cv::aruco::drawAxis` bị xóa trên OpenCV mới, code đã đổi
> sang `cv::drawFrameAxes` nên tự biên dịch được trên máy mới.

### A.5. Giai đoạn A — chi tiết từng bước

**Hai biến bắt buộc ở Terminal 1, không phải ở đâu khác.**
- `GZ_SIM_RESOURCE_PATH` — tiến trình phân giải `model://` là **gz server** do
  PX4 khởi động; đặt trong launch file spawn **không có tác dụng**. Thiếu nó
  box spawn thành công về vật lý (có trong `gz model --list`, controller nạp
  đủ) nhưng **mọi `<visual>` rỗng** → box vô hình, dễ đọc nhầm là "spawn
  hỏng". PX4 **nối thêm** chứ không ghi đè nên export trước là an toàn.
- `PX4_GZ_NO_FOLLOW=1` — bỏ khoá camera Gazebo theo drone. Quên thì:
  `gz topic -t /gui/track -m gz.msgs.CameraTrack -p "track_mode: NONE"`.

**Không có màn hình vẫn chạy được cả vòng.** Thêm `HEADLESS=1` để gz chạy
server không GUI — hợp cho máy chủ, WSL, hay chạy tự động:
```bash
cd ~/PX4 && HEADLESS=1 PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing
```
Đã kiểm: vòng khép kín tới `CHARGING` chạy trọn ở chế độ này. Camera của drone
vẫn render bình thường (tracker vẫn nhận đủ ảnh 1280×720), chỉ mất cửa sổ
Gazebo — nên tiêu chí "nhìn thấy marker" phải kiểm qua `rqt_image_view
/gimbal_camera` hoặc log tracker thay vì nhìn mắt.

Launch T2 chờ **20 giây** rồi mới nạp 4 controller (cố ý): `controller_manager`
nằm trong plugin gz, chỉ khởi động khi box spawn; gọi `load_controller` ngay
lúc nó đang khởi tạo thì phản hồi mất ~15 s, trong khi `spawner`/
`load_controller` hard-code timeout **10 s** ở Humble. Mỗi controller một
tiến trình `spawner` riêng để một cái lỗi không chặn ba cái còn lại — đó là
vì sao có controller còn `unconfigured` cần hoàn tất bằng tay
(`unconfigured → active` không hợp lệ trực tiếp, phải qua hai bước).

`ros2 topic pub` mở nắp dùng `-r 2 -t 6`, **không `--once`**: `--once` hủy
publisher ngay khi vừa gửi, thường trước khi controller discovery xong, và
message rơi mất trong im lặng.

### A.6. Giai đoạn B — chi tiết từng bước

**T7 (HUD) là cửa sổ nên mở suốt lượt chạy.** HUD trả lời cả hai câu quyết
định một lượt drone-in-a-box: *drone có thấy marker chưa* (`Marker Dist /
IDs`) và *box đã mở nắp chưa* (`BOX: <STATE>`, xanh lá ở
`WAITING_FOR_LANDING(7)`). Cách đọc từng dòng:
`ros2_ws/src/precision_landing/README.md`.

**T4 dùng `sitl_mavros.launch.py`, KHÔNG dùng `mavros px4.launch`.**
`px4.launch` không khai báo arg `use_sim_time` nên truyền vào bị **bỏ qua im
lặng**: MAVROS chạy đồng hồ tường trong khi ảnh mang dấu thời gian mô phỏng →
tracker vẽ đỏ `sync N/A: clock mismatch`, độ cao HUD là pose mới nhất chứ
không ứng với khung đang xem.

**T6 fixture chỉ cho SITL.** `dib_bringup.launch.py` là launch **sản phẩm** —
chạy nguyên xi trên phần cứng thật, không phải tắt cờ nào. `sitl_fixtures.launch.py`
publish `/gps` cho box (xem 2.3); trên box thật GPS là thiết bị thật nên bỏ T6.

`/mavros` tự nó không tồn tại — `ros2 param get /mavros ...` trả `Node not
found` là sai tên node (đúng là `/mavros/mavros_node`), không phải MAVROS
hỏng.

`/landing/pose_sync_ms` **chỉ có sau khi drone bay**, đừng dùng làm bước kiểm
tiền bay. Tracker chỉ publish topic này khi ghép được dấu thời gian ảnh với
một pose trong lịch sử; drone còn nằm trên mặt đất thì `ros2 topic echo` báo
`does not appear to be published yet` — đúng, không phải lỗi. Đang bay mà ra
`-1.0` mới là lệch đồng hồ.

**Không có dòng `param set NAV_DLL_ACT 0` thì không arm được.** PX4 mặc định
`NAV_DLL_ACT = 2`, tức đòi phải có kết nối GCS mới cho arm. MAVROS không tính
là GCS. Chạy pipeline này mà không mở QGroundControl thì `commander takeoff`
trả về:
```
WARN  [health_and_arming_checks] Preflight Fail: No connection to the GCS
WARN  [commander] Arming denied: Resolve system health failures first
```
Drone nằm im, FSM đứng ở `IDLE`, và **không có dòng log nào nhắc tới box hay
tracker** — rất dễ đi lùng lỗi nhầm ở phía ROS. Hai cách, chọn một: `param set
NAV_DLL_ACT 0` (hợp cho chạy headless/tự động), hoặc mở QGroundControl trước
khi takeoff (tự nối UDP 14550). Kiểm nhanh khi nghi ngờ: `pxh> commander
check` — phải in `Preflight check: OK`.

Sau bay, kiểm độ ồn log (đếm dòng, không cảm tính):
```bash
# chạy T5 với: ... dib_bringup.launch.py 2>&1 | tee /tmp/bringup.log
wc -l /tmp/bringup.log          # cả chuyến ~2 phút: DƯỚI 40 dòng, KHÔNG dòng lặp theo tick
grep 'Box in' /tmp/bringup.log  # mỗi state đúng MỘT dòng
```

### A.7. Giới hạn đã biết

**Fixture GPS.** `box_simulation` chưa có `ros_gz_bridge` cho sensor `navsat`,
nên trong SITL vẫn phải dùng node fixture publish `/gps`. Trên phần cứng thật
box có GPS thật nên không cần fixture.

**Tốn RAM — gần như toàn bộ là mesh visual của box.** Đo trên máy 16 GB (PSS,
không phải RSS):

| | RAM |
|---|---|
| `gz sim` khi mới có drone + world | **509 MB** |
| `gz sim` sau khi spawn box + marker | **2005 MB** |
| Tất cả node ROS còn lại cộng lại | ~530 MB |
| **Cả pipeline** | **~2.5 GB** |

Chênh 1.5 GB đó đến từ **một file**: `BOX PAD1.0_simple.dae` — 3.58 triệu tam
giác, và nó **chỉ dùng để nhìn** (collision của box là các khối hộp riêng
trong `box.xacro`). Máy dưới 8 GB nên giảm mesh trước khi chạy:

```bash
# ví dụ với blender: giảm còn ~2% số tam giác rồi ghi đè file .dae
blender --background --python-expr "
import bpy; bpy.ops.wm.collada_import(filepath='BOX PAD1.0_simple.dae')
for o in bpy.context.scene.objects:
    if o.type=='MESH':
        m=o.modifiers.new('d','DECIMATE'); m.ratio=0.02
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.modifier_apply(modifier='d')
bpy.ops.wm.collada_export(filepath='BOX PAD1.0_simple.dae')"
```
Mesh này là bản vendor của team khác nên repo giữ nguyên bản gốc; giảm xong
nhớ gzip lại (`gzip -k`) vì repo ship bản `.dae.gz`. `HEADLESS=1` (A.5) cũng bỏ
hẳn tiến trình GUI của Gazebo.

### A.8. Chạy tách domain (M4) — vì sao không dùng DDS-Router

Trên Humble (Fast DDS 2.6) DDS-Router 3.x không discovery được endpoint
Humble, còn 2.2 bắc cầu topic được nhưng **không route reply** của service.
Cầu M4 dự kiến là `domain_bridge` (ROS-native) — xử lý cả topic lẫn service,
không sửa dòng code hợp đồng nào. Cách chạy dự kiến khi package vào repo:
box terminal `export ROS_DOMAIN_ID=42`, drone terminal `export
ROS_DOMAIN_ID=0`, T5 thêm `include_telemetry_bridge:=false` (đẩy
`mavros_to_dib_telemetry` sang domain drone), cộng một terminal cầu
`ros2 run dib_domain_bridge dib_split_bridge 42 0`.
