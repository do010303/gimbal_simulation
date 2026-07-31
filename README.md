# PX4 Gimbal Precision Landing

Pipeline hạ cánh chính xác cho drone `x500_gimbal` trong Gazebo SITL bằng
**Fractal ArUco** (tracker C++ `aruco_fractal_tracker`, marker fractal lồng nhau
cạnh ngoài 50 cm) qua **MAVROS**. Mốc hiện tại: **M3 — drone-in-a-box khép trọn
vòng đời tới `CHARGING`** (mục 2). Chi tiết M3: `docs/m3.md`.

---

## 1. Cài đặt

### 1.1. Điều kiện tiên quyết (ngoài repo)

- ROS 2 Humble (đã source).
- **Gazebo Harmonic** (`gz sim --version` → 8.x). Đã kiểm trên 8.11.0.
- PX4-Autopilot checkout ở `~/PX4`, build được SITL. Để chỗ khác cũng chạy —
  chỉ cần thay `~/PX4` trong mọi lệnh dưới đây cho khớp.
- **`gz_ros2_control` build TỪ NGUỒN cho Harmonic** (mục 1.1.1).

#### 1.1.1. Build `gz_ros2_control` cho Harmonic

Bản apt `ros-humble-gz-ros2-control` là cho **Fortress**. Để nguyên thì gz server
**segfault ngay khi spawn box**: plugin *system* (Harmonic) nạp plugin *hardware*
qua pluginlib và vớ phải bản Fortress — `v8::EntityComponentManager` truyền vào
hàm nhận `v6::`. Chi tiết ở "Bẫy P1.4" trong `docs/m3.md`.

```bash
# 1. Gỡ bản apt Fortress (kiểm không gói nào phụ thuộc — kết quả phải RỖNG)
apt-cache rdepends --installed ros-humble-gz-ros2-control
sudo apt remove ros-humble-gz-ros2-control

# 2. Build từ nguồn, nhánh humble
mkdir -p ~/gz_ros2_control_ws/src && cd ~/gz_ros2_control_ws/src
git clone -b humble https://github.com/ros-controls/gz_ros2_control.git
cd ~/gz_ros2_control_ws

# 3. GZ_VERSION QUYẾT ĐỊNH build cho Harmonic hay Fortress — phải export TRƯỚC
#    (CMakeLists đọc $ENV{GZ_VERSION}: 'harmonic' -> gz-sim8, mặc định -> Fortress)
export GZ_VERSION=harmonic
rosdep install -r --from-paths src -i -y --rosdistro humble
colcon build --symlink-install
```

Kiểm — cả **hai** `.so` phải cùng là bản Harmonic vừa build:
```bash
ls ~/gz_ros2_control_ws/install/gz_ros2_control/lib/libgz_ros2_control-system.so \
   ~/gz_ros2_control_ws/install/gz_ros2_control/lib/libgz_hardware_plugins.so
dpkg -l ros-humble-gz-ros2-control 2>/dev/null | grep '^ii' && echo "!! bản apt Fortress VẪN CÒN"
```

> **Không gỡ bản apt thì vẫn chạy được** nếu terminal chạy `make px4_sitl` đã
> source ws này trước (mục 2.2) — nhưng chỉ cần một terminal quên source là
> segfault quay lại. Gỡ hẳn thì hết đường nạp nhầm.

### 1.2. Clone-and-run (M1–M3)

```bash
# 1. Clone vào cây PX4
cd ~/PX4/examples
git clone <repo-url> SITL_PrecisionLanding
cd SITL_PrecisionLanding

# 2. Đồng bộ world/model/texture sang cây PX4 (gz server của PX4 load từ đây)
cd ~/PX4 && rsync -a examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/ Tools/simulation/gz/
cd examples/SITL_PrecisionLanding

# 3. px4_msgs (clone riêng, không nằm trong repo)
git clone https://github.com/PX4/px4_msgs.git ros2_ws/src/px4_msgs

# 4. Verify: cài dep + build libaruco + GIẢI NÉN mesh box + kiểm dep ngoài
source /opt/ros/humble/setup.bash
chmod +x verify_build_env.sh && ./verify_build_env.sh     # dừng và sửa nếu báo FAIL/WARN

# 5. Build
cd ros2_ws && colcon build --symlink-install && source install/setup.bash && cd ..

# 6. Chạy pipeline drone-in-a-box: xem mục 2 (6 terminal)
```

`box_manager`, `box_simulation`, `dib_msgs`, `precision_landing`,
`aruco_fractal_tracker` đã nằm trong repo. `verify_build_env.sh` lo: gói
ROS/bridge còn thiếu, `libaruco 3.1.12` (từ `aruco_build/aruco.zip`), gunzip mesh
thân box, và kiểm `px4_msgs`/`gz_ros2_control`.

> **Kiểm tra tài nguyên đã sync** (sau bước 2):
> ```bash
> ls ~/PX4/Tools/simulation/gz/worlds/fractal_aruco_landing.sdf
> ls ~/PX4/Tools/simulation/gz/models/{fractal_aruco_marker,dib_box_marker}/model.sdf
> grep horizontal_fov ~/PX4/Tools/simulation/gz/models/gimbal/model.sdf   # phải là 1.4137
> ```
> **Camera gimbal phải có `horizontal_fov` = 1.4137 rad (81°), 1280×720.** Bản
> upstream của submodule `Tools/simulation/gz` để `2.0` rad (114.6°) — rsync ở
> bước 2 ghi đè lại đúng giá trị. Sai FOV thì marker chiếm ít pixel hơn ~1.8 lần
> ở cùng khoảng cách: tracker vẫn chạy (nó lấy nội tham số từ `camera_info` nên
> ước lượng pose vẫn tự nhất quán), nhưng tầm bắt marker và các ngưỡng
> approach/descend đã tinh chỉnh trong `offboard_precland_params.yaml` **không
> còn là cấu hình đã đo ra PASS 8/8**. Đây cũng là FOV mà `aruco_fractal_tracker`
> ghi cứng làm giá trị dự phòng (`fx = fy = 749.338`).
>
> World `fractal_aruco_landing.sdf` **không còn** `<include> dib_box_landing_pad`:
> marker giờ nằm trên box khớp động (`box_simulation`), spawn bằng
> `box_spawn_only.launch.py`. Để cả hai sẽ có **hai marker giống hệt** → tracker
> bám nhầm, drone hạ xuống pad tĩnh (log/FSM vẫn *trông như* đúng). Cách khôi phục
> pad tĩnh nằm trong chú thích file world.

> **Mesh thân box ship nén.** `BOX PAD1.0_simple.dae` (visual, 270 MB) vượt giới
> hạn 100 MB/file của GitHub nên repo chỉ chứa `.dae.gz` (64 MB);
> `verify_build_env.sh` tự gunzip trước build. Box **vô hình** sau build ⇒ chưa
> gunzip, chạy lại verify. (Mesh nắp/kẹp nhỏ nằm thẳng trong repo; `base_link_1.dae`
> bỏ vì không dùng. `box_manager`/`box_simulation` được vendor thẳng vào
> `ros2_ws/src/`.)

### 1.3. Cài gói thủ công (nếu không chạy verify script)

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
`px4_msgs` phải nằm trong `ros2_ws/src/` hoặc source từ workspace khác trước khi build.

### 1.4. Xử lý sự cố ArUco (`libaruco`)

Thư viện fractal là **ArUco C++ 3.1.12** (KHÔNG phải `opencv-contrib-python`),
build vào `$HOME/.local`.

| Triệu chứng | Cách sửa |
|---|---|
| `colcon` báo `Could not find a package configuration file provided by "aruco"` | Chưa build libaruco → chạy lại `./verify_build_env.sh` (unzip + cmake + `make install` vào `$HOME/.local`). |
| Runtime `error while loading shared libraries: libaruco.so.3.1` | `export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH` (nên thêm vào `~/.bashrc`). |
| verify báo thiếu `aruco_build/aruco.zip` | File 1.6 MB này phải có trong clone — kiểm `.gitignore`. |
| CMake vớ phải libaruco cũ ở `/usr/local` gây version lệch | Gỡ bản cũ, hoặc build với `CMAKE_PREFIX_PATH=$HOME/.local`. |

Kiểm: `find $HOME/.local /usr/local/lib -name 'libaruco.so*'`. Rebuild riêng tracker:
```bash
cd ros2_ws && colcon build --symlink-install --packages-select aruco_fractal_tracker --cmake-clean-cache
```

> **OpenCV 4.7+:** `cv::aruco::drawAxis` bị xóa trên OpenCV mới, code đã đổi sang
> `cv::drawFrameAxes` nên tự biên dịch được trên máy mới.

### 1.5. Dọn tiến trình cũ (chạy trước mỗi lần bắt đầu)

```bash
pkill -f 'px4|gz sim|gzserver|ruby.*gz|robot_state_publisher|spawner|controller_manager'
pkill -f 'mavros|offboard_precland|aruco_fractal|box_state_manager|box_hardware'
ros2 daemon stop            # QUAN TRỌNG — xem bên dưới
sleep 2; pgrep -af 'px4|gz sim' || echo "sach"
```

Bỏ qua bước này là nguyên nhân phổ biến nhất khiến máy lag và lần chạy sau hỏng
theo kiểu khó hiểu (giữ UDP endpoint / quyền điều khiển gimbal từ phiên trước).

> **`ros2 daemon stop` không phải cho vui.** Daemon cache thông tin discovery
> giữa các phiên và các `ROS_DOMAIN_ID`. Daemon cũ còn sống thì `ros2 node list`
> / `ros2 topic list` / `ros2 topic echo` **im lặng trả về rỗng** dù node đang
> chạy ngon — đúng những lệnh mà 3 bước kiểm tiền bay ở mục 2.4 dựa vào, nên rất
> dễ kết luận nhầm là pipeline hỏng. Nghi ngờ thì thêm `--no-daemon` vào lệnh
> `ros2` để hỏi thẳng, bỏ qua cache.

---

## 2. Drone-in-a-Box — Pipeline Đầy Đủ (M3)

> **Mốc M3 — ✅ PASS 8/8 (2026-07-29), sai số hạ cánh thật 4.9 cm.** Mục này là
> **dòng chạy**. Chi tiết đầy đủ (thiết kế bắt tay, hợp nhất world, khép vòng đời,
> nhật ký bẫy, tiêu chí từng bước): **`docs/m3.md`**. File test:
> **`docs/m3_box_handshake_test/`**.

Toàn bộ hệ thống trong **một world Gazebo duy nhất**: drone `x500_gimbal` bắt tay
với box qua service `dib_msgs`, box thật (nắp + kẹp điều khiển bằng ros2_control)
mở nắp đón, drone hạ cánh thị giác xuống marker fractal trên sàn box, box kẹp giữ
drone, drone xin tắt nguồn, box chuyển sang sạc — vòng đời `EMPTY → … → CHARGING`
khép trọn.

```
box_manager  ──service──▶  box_hardware_adapter  ──JointTrajectory──▶  ros2_control
     ▲                                                                      │
     └──────────────  /joint_states  ◀──────────  Gazebo (cùng world)  ◀─────┘
                                                        │
drone: MAVROS ──▶ mavros_to_dib_telemetry ──▶ box_manager
       camera ──▶ aruco_fractal_tracker ──▶ offboard_precland_controller ──▶ MAVROS
```

### 2.1. Thành phần

| Package | Vai trò |
|---|---|
| `precision_landing` | Tracker fractal + `offboard_precland_controller` (FSM hạ cánh, C++) + `mavros_to_dib_telemetry` |
| `box_manager` | FSM box (`EMPTY → PREPARING_FOR_LANDING → WAITING_FOR_LANDING → SECURING_DRONE → CHARGING`) |
| `box_hardware_adapter` | Dịch service `box_manager` ↔ `JointTrajectory` cho ros2_control; `/joint_states` → `/lid/status`, `/clamp/status` |
| `box_simulation` | Model box khớp động (nắp, 2 cặp kẹp) |
| `dib_box_marker` | Marker fractal 0.50 m trên sàn box |

Launch file (đều trong `precision_landing`, trừ fixture):

| Launch | Khởi động gì |
|---|---|
| `sitl_precland.launch.py` | gz bridge + tracker + `offboard_precland_controller` |
| `sitl_mavros.launch.py` | MAVROS **có `use_sim_time`** (xem 2.4) |
| `dib_bringup.launch.py` | adapter + FSM box + cầu telemetry (**chỉ 3 node sản phẩm**, chạy nguyên xi trên phần cứng thật) |
| `docs/m3_box_handshake_test/sitl_fixtures.launch.py` | fixture GPS box, **chỉ SITL** |

### 2.2. Header cho MỌI terminal

```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

### 2.3. Giai đoạn A — dựng world và kiểm box/marker (2 terminal)

Chạy riêng giai đoạn này trước: nếu marker không hiện thì cả pipeline chắc chắn
thất bại, mà giai đoạn A chỉ tốn 2 tiến trình thay vì 6.

**Terminal 1 — PX4 + Gazebo:**
```bash
export GZ_SIM_RESOURCE_PATH=$HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share
cd ~/PX4 && PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing
```

> **Hai biến này bắt buộc ở Terminal 1, không phải ở đâu khác.**
> - `GZ_SIM_RESOURCE_PATH` — tiến trình phân giải `model://` là **gz server** do
>   PX4 khởi động; đặt trong launch file spawn **không có tác dụng**. Thiếu nó box
>   spawn thành công về vật lý (có trong `gz model --list`, controller nạp đủ)
>   nhưng **mọi `<visual>` rỗng** → box vô hình, dễ đọc nhầm là "spawn hỏng". PX4
>   **nối thêm** chứ không ghi đè nên export trước là an toàn.
> - `PX4_GZ_NO_FOLLOW=1` — bỏ khoá camera Gazebo theo drone. Quên thì:
>   `gz topic -t /gui/track -m gz.msgs.CameraTrack -p "track_mode: NONE"`.

> **Không có màn hình vẫn chạy được cả vòng.** Thêm `HEADLESS=1` để gz chạy
> server không GUI — hợp cho máy chủ, WSL, hay chạy tự động:
> ```bash
> cd ~/PX4 && HEADLESS=1 PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing
> ```
> Đã kiểm: vòng khép kín tới `CHARGING` chạy trọn ở chế độ này. Camera của drone
> vẫn render bình thường (tracker vẫn nhận đủ ảnh 1280×720), chỉ mất cửa sổ
> Gazebo — nên tiêu chí "nhìn thấy marker" của Giai đoạn A phải kiểm qua
> `rqt_image_view /gimbal_camera` hoặc log tracker thay vì nhìn mắt.

Đợi tới dấu nhắc `pxh>` rồi mới sang Terminal 2.

**Terminal 2 — spawn box + marker vào chính world đó:**
```bash
ros2 launch box_simulation box_spawn_only.launch.py
```

Launch chờ **20 giây** rồi mới nạp 4 controller (cố ý): `controller_manager` nằm
trong plugin gz, chỉ khởi động khi box spawn; gọi `load_controller` ngay lúc nó
đang khởi tạo thì phản hồi mất ~15 s, trong khi `spawner`/`load_controller`
hard-code timeout **10 s** ở Humble. Mỗi controller một tiến trình `spawner`
riêng để một cái lỗi không chặn ba cái còn lại.

**Kiểm (sau Terminal 2 ~40 giây):**
```bash
gz model --list                       # có Box và dib_box_marker
gz model -m Box -p                    # [2.5 -2.0 0.78233] [1.5708 0 0]
ros2 control list_controllers         # 4 dòng, tất cả 'active'
ros2 topic echo --once /joint_states  # 6 joint
```

Controller nào còn `unconfigured` thì nó **đã nạp**, chỉ mất nửa sau do timeout —
hoàn tất bằng tay, **hai bước** (`unconfigured → active` không hợp lệ trực tiếp):
```bash
ros2 control set_controller_state joint_state_broadcaster configure
ros2 control set_controller_state joint_state_broadcaster active
```

**Mở nắp và xác nhận marker:**
```bash
ros2 topic pub -r 2 -t 6 /joint_lid_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["lid_left_joint"], points: [{positions: [1.57], time_from_start: {sec: 2}}]}'
```
> Dùng `-r 2 -t 6`, **không `--once`**: `--once` hủy publisher ngay khi vừa gửi,
> thường trước khi controller discovery xong, và message rơi mất trong im lặng.

Nhìn vào lòng box: phải thấy ô marker fractal đen-trắng trên mặt sàn.

### 2.4. Giai đoạn B — vòng kín (thêm 4 terminal)

Giữ nguyên Terminal 1 và 2. Tổng **6 terminal**: ba node phía box gom vào một
launch, fixture SITL tách riêng.

| T | Lệnh | Vai trò |
|---|---|---|
| 3 | `ros2 launch precision_landing sitl_precland.launch.py` | bridge + tracker + controller |
| 4 | `ros2 launch precision_landing sitl_mavros.launch.py` | MAVROS (đồng hồ mô phỏng) |
| 5 | `ros2 launch precision_landing dib_bringup.launch.py` | **cả 3 node phía box** trong một terminal |
| 6 | `ros2 launch ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/sitl_fixtures.launch.py` | fixture **chỉ SITL** |

> **T4 dùng `sitl_mavros.launch.py`, KHÔNG dùng `mavros px4.launch`.** `px4.launch`
> không khai báo arg `use_sim_time` nên truyền vào bị **bỏ qua im lặng**: MAVROS
> chạy đồng hồ tường trong khi ảnh mang dấu thời gian mô phỏng → tracker vẽ đỏ
> `sync N/A: clock mismatch`, độ cao HUD là pose mới nhất chứ không ứng với khung
> đang xem.

> **T6 fixture chỉ cho SITL.** `dib_bringup.launch.py` là launch **sản phẩm** —
> chạy nguyên xi trên phần cứng thật, không phải tắt cờ nào. `sitl_fixtures.launch.py`
> publish `/gps` cho box (xem 2.5); trên box thật GPS là thiết bị thật nên T6 bỏ đi.

**Kiểm 3 thứ trước khi bay** (10 giây bây giờ, tránh mất cả lượt bay):
```bash
ros2 topic echo --once --field data /landing/pose_sync_ms   # số dương (vd 40.0), KHÔNG -1.0
ros2 param get /mavros/mavros_node use_sim_time             # True  (node thật là /mavros/mavros_node)
ros2 control list_controllers                               # 4 dòng 'active'
```
Lệnh 1 là **bằng chứng** (đo lệch thật giữa dấu thời gian ảnh và pose); lệnh 2 chỉ
xác nhận nguyên nhân. `/mavros` tự nó không tồn tại — `ros2 param get /mavros ...`
trả `Node not found` là sai tên node, không phải MAVROS hỏng.

Giám sát (mở khi cần):
```bash
ros2 run rqt_image_view rqt_image_view /precision_landing/debug_image
ros2 topic echo --field data /landing/pose_sync_ms          # ms; -1 = lệch đồng hồ
python3 docs/m3_box_handshake_test/m3_full_loop_monitor.py  # chấm điểm 8 tiêu chí
```

**Bay**, trong `pxh>` của Terminal 1:
```
pxh> commander takeoff
pxh> commander land
```
`offboard_precland_controller` bắt `AUTO.LAND`, tự chuyển `OFFBOARD` và chạy
`GOTO_BOX → PRELANDING_CHECK → WAIT_BOX_READY → START`. **FSM đứng ở `IDLE` khi
chưa bay là ĐÚNG** — controller chỉ rời `IDLE` khi MAVROS báo drone đang bay.

Sau bay, kiểm độ ồn log (đếm dòng, không cảm tính):
```bash
# chạy T5 với: ... dib_bringup.launch.py 2>&1 | tee /tmp/bringup.log
wc -l /tmp/bringup.log          # cả chuyến ~2 phút: DƯỚI 40 dòng, KHÔNG dòng lặp theo tick
grep 'Box in' /tmp/bringup.log  # mỗi state đúng MỘT dòng
```

### 2.5. Ba cấu hình sai là hỏng cả lần chạy

1. **`box_id` phải khớp hai file.** `box_state_manager.yaml` dùng `box_id: 2`, nên
   `offboard_precland_params.yaml` cũng phải `2`. Lệch nhau thì drone gọi `b1/cmd`
   (không tồn tại), chờ `/b1/telemetry` (không ai publish) → `box_telemetry_valid_`
   mãi false → FSM **bỏ qua toàn bộ bắt tay** mà không báo lỗi. Xác nhận bằng log:
   `Derived box_telemetry_topic='/b2/telemetry' from box_id=2`.

2. **Box phải có toạ độ GPS.** `box_state_manager` đọc vị trí box từ topic `gps`
   (`sensor_msgs/NavSatFix`). SITL **không ai publish** (sensor `navsat` của
   `box_simulation` chưa có `ros_gz_bridge`) → `box_info.lat/lon = 0`,
   `st_goto_box()` tính setpoint cách hàng nghìn km, drone bay mất. Fixture T6
   publish `/gps` tại marker ENU `(2.5129, −2.5896)`: `lat 47.397947795 lon 8.546197088`.

3. **`marker_size` phải khớp plane thật.** `marker.png` có viền trắng 1 module nên
   marker **đen** chỉ chiếm 80.12% cạnh ảnh. Để marker đen đúng 0.50 m (`marker_size`
   trong `offboard_precland_params.yaml`) thì plane phải `0.50 / 0.8012 = 0.6241 m`.
   Đổi một số phải đổi số kia, nếu không pose sai **thang đo** → sai độ cao → flare
   sớm hoặc cắm xuống.

### 2.6. Dấu hiệu chạy đúng

FSM drone và box đan xen theo đúng quan hệ nhân quả:
```
DRONE  -> GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY
BOX    -> PREPARING_FOR_LANDING(6) -> WAITING_FOR_LANDING(7)
DRONE  -> START -> HORIZONTAL_APPROACH -> DESCEND_ABOVE_TARGET -> FINAL_APPROACH
MAVROS -> landed_state=ON_GROUND
BOX    -> SECURING_DRONE(8) -> CHARGING(9)
```
- Box chỉ rời `EMPTY` **sau** khi drone vào `WAIT_BOX_READY` → chính `REQUEST_LANDING` của drone gây ra.
- Drone chỉ vào `START` **sau** khi box báo `WAITING_FOR_LANDING` → không chạy trước nắp box.
- **Không có** `SEARCH` kéo dài, **không có** `FALLBACK`.

Vòng đời khép tới `CHARGING` — **sau khi drone chạm đất còn ~35–40 giây nữa**,
đừng tắt sớm:
```
offboard_precland: LANDING COMPLETE — disarmed. Waiting for box to secure and charge.
box_state_manager: Box in SECURING_DRONE state, securing state: 5   (kẹp + đóng nắp)
offboard_precland: BoxLink: sending TURN_OFF_DRONE to b2 (agent_id=12)
box_hardware_adapter: /dock/power_button/cmd command=0 -> drone power OFF
mavros_to_dib_telemetry: Dock power OFF: stopping publishing d1/telemetry
box_state_manager: Box in CHARGING state
offboard_precland: Box reached CHARGING — drone-in-a-box cycle complete
```
`TURN_OFF_DRONE` gửi lặp mỗi 3 giây là **đúng thiết kế** (idempotent, box giữ như
cờ dính, chỉ tiêu thụ khi kẹp/nắp đóng xong).

> **Vì sao phải giả lập cú cắt điện.** `box_manager` rời `POWER_OFF → DONE` (rồi
> `CHARGING`) khi telemetry drone **im quá 5 giây**. Phần cứng thật: box cắt nguồn
> nên máy đồng hành tắt, im lặng miễn phí. SITL: MAVROS chạy mãi, nên adapter
> publish `/dock/drone_power` và `mavros_to_dib_telemetry` ngừng phát khi nhận
> `false`. Thiếu mắt xích này thì box kẹt ở `POWER_OFF` vĩnh viễn.

Dòng `Ground contact: blocked by 20.5cm → force-disarm` **không phải lỗi**: drone
dừng cao hơn mặt đất 0.6 m vì đang đứng trên box; nhánh force-disarm xử lý đúng.
Marker fractal tự rụng tầng theo độ cao (`ids=[0,1,2]` trên cao → `ids=[1,2]` ở
~0.65 m khi tầng ngoài 0.50 m ra khỏi khung).

### 2.7. Đọc HUD và số latency cho đúng (quan trọng khi chạy HITL)

`E2E latency (image → debug) = now() − image_stamp` **chỉ là độ trễ khi hai đầu
chung một đồng hồ**. Nếu camera đóng dấu bằng đồng hồ riêng hoặc NTP lệch, cùng
phép trừ ấy cho ra **độ lệch đồng hồ** trông y hệt độ trễ khổng lồ — lý do HITL
báo e2e latency rất lớn trên máy nhúng trong khi `Detector processing` (đo bằng
`steady_clock`, miễn nhiễm) chỉ vài ms. Phân biệt bằng **hình dạng**:

| | sàn (floor) | dao động (jitter) |
|---|---|---|
| Độ trễ thật | nhỏ | thấy rõ, đổi từng khung |
| Lệch đồng hồ | lớn | gần bằng 0 |

Tracker theo dõi sàn trượt 10 giây và tự gắn cờ (`[CLOCK OFFSET? floor=2478 jitter=2]`);
thấy cờ này thì **đừng đi tối ưu hiệu năng**, hãy đồng bộ thời gian trước. Cửa sổ
chấp nhận đã siết từ 60 s xuống 2 s.

`UAV ENU U` và `MARKER DIST` **không bằng nhau, và đó là đúng** — đo từ hai gốc:
`U` từ điểm **cất cánh**, `MARKER DIST` từ **camera** tới marker trên nóc box.
```
U − MARKER DIST ≈ cao độ marker − cao độ camera so với base_link ≈ 0.637 − 0.118 = 0.52 m
```
(0.118 đọc từ model: gimbal `z=+0.28`, sensor `z=−0.162` → camera cao hơn base_link
0.118 m. Log bay giữ hiệu này **hằng số 0.48–0.54 m** — hằng số chứ không tỷ lệ,
loại trừ sai `marker_size`.)

Mỗi độ cao có tên riêng: `alt_agl` (so điểm cất cánh, dùng ở `[YAW-3D]`/`FINAL_APPROACH`),
`alt_pad` (so marker, dùng ở `APPROACH`/`DESCEND`). Vị trí tách chủ thể:
```
FINAL_APPROACH: t=1.2s drone=(2.51,-2.59, alt_agl 0.621m) aim=(2.52,-2.50) ...
TOUCHDOWN: drone=(2.5104,-2.5863) aim=(2.5200,-2.5000) aim_error=0.090m alt_agl=0.664m
```
`drone=` là vị trí thật; `aim=` là điểm ngắm (ước lượng marker của tracker). Sai số
hạ cánh THẬT = `drone=` (dòng `TOUCHDOWN`) trừ marker thật `(2.5129, −2.5896)`;
`aim_error` là chất lượng bám của vòng điều khiển.

> Các số "sai số hạ cánh" ghi **trước 2026-07-23** lấy từ `final_xy` = điểm ngắm,
> nên thực ra là sai số **ước lượng marker của tracker** — đừng so với `TOUCHDOWN`.

### 2.8. Chỉnh hướng đậu của drone (`marker_yaw`)

Tracker suy một góc yaw từ marker và controller khoá drone vào đó — **xoay marker
là xoay hướng drone đậu**. Mặc định `marker_yaw = 1.5708` (90°). Đổi ngay trên
dòng lệnh, **chỉ khởi động lại Terminal 2, không phải PX4**:
```bash
ros2 launch box_simulation box_spawn_only.launch.py marker_yaw:=1.5708
```
Thử `0.0` / `1.5708` / `3.1416` / `-1.5708`, giữ giá trị nào đậu drone thẳng hàng
giữa hai cặp kẹp.

> Tiêu chí là **hai cặp kẹp**, không phải màu nắp. Kẹp đóng theo world Y (0.774 m)
> và world X (0.782 m) nên thân drone phải nằm dọc hai trục đó. Chọn theo mắt nhìn
> nắp có thể lệch 90° so với kẹp.

### 2.9. Giới hạn đã biết

`box_simulation` chưa có `ros_gz_bridge` cho sensor `navsat`, nên trong SITL vẫn
phải dùng node fixture publish `/gps` (mục 2.5). Trên phần cứng thật, box có GPS
thật nên không cần fixture.

---

## 3. Precision Landing — các pipeline cũ (legacy)

Các pipeline hạ cánh thị giác trước M3, giữ lại để tham chiếu. **Khung 4 terminal
chung** cho các biến thể SITL:

```bash
# Dọn tiến trình cũ (mục 1.5)

# T1 — PX4 SITL:
cd ~/PX4 && PX4_GZ_WORLD=fractal_aruco_landing PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal

# T2 — MAVROS (chạy một lần, GIỮ NGUYÊN — đừng restart giữa chuyến bay):
source /opt/ros/humble/setup.bash
ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580
#   kiểm: ros2 topic echo --once /mavros/state   ->   connected: true

# T3 — bridge camera + tracker + lander (CHỌN launch theo biến thể, xem bảng dưới):
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch <package> <launch-file>

# T4 — HUD overlay:
ros2 run rqt_image_view rqt_image_view      # chọn topic /landing/annotated_image
```

Các launch T3 **không** khởi động MAVROS; sửa/restart tracker hoặc lander thì chỉ
restart T3, giữ nguyên T2 để PX4 vẫn nhận heartbeat mission computer.

| Biến thể | T3 launch |
|---|---|
| **3.1** Fractal ArUco (MAVROS) | `ros2 launch px4_offboard fractal_aruco_landing.launch.py` |
| **3.2** QGC sim precland | `ros2 launch px4_offboard qgc_sim_precland.launch.py` |
| **3.3** QGC offboard precland | `ros2 launch px4_offboard qgc_offboard_precland.launch.py` |
| **3.4** precision_landing (C++) | `ros2 launch precision_landing sitl_precland.launch.py` |

Cấu hình SITL (3.1): box `x=4.0, y=-3.5, yaw=0`; marker 0.50 m trên
`dib_box_landing_pad`; camera 1280×720 @30 Hz, hFOV 1.4137 rad (81°); control loop
30 Hz (nghiệm thu ≥20 Hz). Ba tầng fractal: 50 / 12.5 / 3.125 cm.
`model.sdf` + `marker_size` + marker vật lý phải cùng kích thước; detector dùng
`custom_fractal.yml`. Nếu PX4 không ở `~/PX4`, truyền
`marker_configuration:=/abs/path/custom_fractal.yml`.

Controller dùng ENU (`search_x=East`, `search_y=North`; `pos_enu/target_enu/…` đều ENU).

### 3.5. Bài bay tự động qua service (dùng với 3.4)

```bash
# T5:
source ~/test_req/install/setup.bash
ros2 launch ros2_telemetry plan_upload.launch.py drone_id:=d1
# T6:
ros2 service call /d1/mission_upload dib_msgs/srv/MissionUpload "{mission: [
  {command: 22, param1: 0.0, param2: 0.0, latitude: 47.397929,  longitude: 8.546217, altitude: 15.0},
  {command: 16, param1: 5.0, param2: 0.0, latitude: 47.39797,   longitude: 8.546322, altitude: 15.0},
  {command: 16, param1: 5.0, param2: 0.0, latitude: 47.3979298, longitude: 8.546217, altitude: 15.0},
  {command: 23, param1: 0.0, param2: 0.0, latitude: 47.3979298, longitude: 8.546217, altitude: 0.0}
]}"
```

### 3.6. Box Hybrid Landing (prototype)

FSM hybrid thay lander cũ, dùng chung PX4 SITL / MAVROS / tracker. Box thật thay
bằng `sim_box_manager` (`/sim_box/state`). T3 đổi sang:
```bash
ros2 launch px4_offboard box_hybrid_landing.launch.py
ros2 topic pub --once /box_hybrid_landing/trigger std_msgs/msg/String "data: 'land'"
```
Node không tự bay mission; dùng QGC/mission thật đưa UAV tới box fixture `(4.0,-3.5)`,
`manual_drive_alt=10.0m` là độ cao acquire ban đầu, rồi mới `REQUEST_LANDING` +
visual guidance. Tuỳ chọn: `enable_offboard_visual_servo:=true`,
`enable_yaw_setpoint:=true yaw_gate_deg:=5.0` (chỉ bật sau khi chắc mode/setpoint
không xung đột PX4/MAVROS). Kiểm:
`ros2 topic echo /box_hybrid_landing/{state,box_state,comms}`.

### 3.7. Camera thật (RTSP, không cần PX4)

Kiểm nhận diện của camera vật lý (SIYI A8 Mini / camera IP) mà chưa cần SITL/FCU:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch precision_landing real_fractal_detect.launch.py enable_mavros:=false
ros2 run rqt_image_view rqt_image_view      # topic /siyi/fractal_debug
ros2 topic echo /siyi/fractal_pose          # luồng pose
```
Đổi RTSP/calibration ở `ros2_ws/src/precision_landing/config/rtsp_publisher_params.yaml`.
Biến thể `siyi_camera_bridge` (truyền tham số trực tiếp thay vì qua file):
```bash
ros2 launch siyi_camera_bridge real_fractal_detect.launch.py enable_mavros:=false \
  rtsp_url:=rtsp://192.168.168.16:8554/main.264 marker_size:=0.162 flip_180:=false \
  marker_configuration:=$PWD/px4/Tools/simulation/gz/models/fractal_aruco_marker/custom_fractal.yml
```

---

## 4. Giám sát, kiểm tra nhanh, ghi chú

### 4.1. Kiểm tra nhanh các topic

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash

ros2 topic hz /gimbal_camera                          # camera bridge
ros2 topic hz /landing/target_camera                  # tracker target
ros2 topic echo --once /landing/target_camera
ros2 topic hz /mavros/setpoint_position/local         # setpoint (timer 30Hz, cần ≥20Hz khi OFFBOARD)
ros2 topic echo --once /mavros/state                  # connected: true
ros2 topic echo /lander/state                         # FSM lander (legacy)
```

### 4.2. Dấu hiệu thành công (legacy pipelines)

```text
Marker detected
State: SEARCH -> HORIZONTAL_APPROACH -> DESCEND_OVER_TARGET
Final altitude reached
PX4 land detector reports landed
LANDING COMPLETE
```
Không dùng force-disarm làm tiêu chuẩn thành công khi chạy thật. Quy trình nghiệm
thu Fractal ArUco + sơ đồ FSM: `docs/FLIGHT_TEST.md`, `docs/fractal_aruco_fsm.png`.

### 4.3. Ghi chú

- Thống nhất mọi marker chính về `0.50 m` (`marker_size:=0.50`); đổi physical size
  trong `model.sdf` thì phải đổi `marker_size` trong launch tương ứng.
- `command 520 unsupported` là capability request MAVLink cũ, không phải lệnh landing.
- Đang giữ OFFBOARD / giữa chuyến bay: **không restart MAVROS** — giữ T2 riêng, chỉ
  restart T3. Restart MAVROS lúc đó có thể gây `Critical: Connection to mission computer lost`.
