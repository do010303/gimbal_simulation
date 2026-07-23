# PX4 Gimbal Precision Landing

Project này chứa pipeline hạ cánh chính xác cho drone `x500_gimbal` trong mô phỏng Gazebo SITL sử dụng **Fractal ArUco landing** (bộ tracker C++ `aruco_fractal_tracker` với cấu trúc marker lồng nhau nested fractal marker tùy chỉnh có kích thước ngoài cùng 50 cm), sử dụng **MAVROS** làm giao thức kết nối điều khiển chính.

---

## Cấu Trúc Thư Mục & Đồng Bộ Mô Phỏng

1. **Clone Dự Án**: Clone repository này vào thư mục `examples` của cây thư mục PX4 checkout:

   ```bash
   cd ~/PX4/examples
   git clone git@github.com:TeedeeTD/SITL_PrecisionLanding.git
   ```

   Cấu trúc thư mục mong đợi:
   ```text
   ~/PX4
   └── examples
       └── SITL_PrecisionLanding
   ```

2. **Đồng Bộ Hóa Mô Phỏng (Sync Worlds, Models & Textures)**:
   PX4 Gazebo sẽ load các world và model từ thư mục nội bộ của PX4. Đồng bộ hóa toàn bộ tài nguyên mô phỏng (bao gồm các file world `.sdf`, mô hình `x500_gimbal`, mô hình marker Fractal `fractal_aruco_marker`, và mô hình box `dib_box_landing_pad`) bằng lệnh `rsync`:

   ```bash
   cd ~/PX4
   rsync -a \
     examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/ \
     Tools/simulation/gz/
   ```

3. **Kiểm tra các tệp tin chính**:

   ```bash
   # Kiểm tra worlds
   ls ~/PX4/Tools/simulation/gz/worlds/fractal_aruco_landing.sdf

   # Kiểm tra mô hình và kết cấu ảnh của Fractal
   ls ~/PX4/Tools/simulation/gz/models/fractal_aruco_marker/model.sdf
   ls ~/PX4/Tools/simulation/gz/models/fractal_aruco_marker/marker.png
   ls ~/PX4/Tools/simulation/gz/models/fractal_aruco_marker/custom_fractal.yml

   # Kiểm tra mô hình box landing pad
   ls ~/PX4/Tools/simulation/gz/models/dib_box_landing_pad/model.sdf

   # M3.5 — marker fractal gắn lên box khớp động (xem mục 4)
   ls ~/PX4/Tools/simulation/gz/models/dib_box_marker/model.sdf
   ```

   > **Lưu ý về `fractal_aruco_landing.sdf` sau M3.5.** World này **không còn
   > `<include>` `dib_box_landing_pad`**. Marker giờ nằm trên box khớp động
   > (`box_simulation`) do `box_spawn_only.launch.py` spawn vào. Nếu để cả hai
   > thì world sẽ có **hai marker fractal giống hệt nhau**, tracker bám vào cái
   > nào rõ hơn và drone hạ xuống pad tĩnh thay vì vào lòng box — trong khi mọi
   > log và FSM vẫn *trông như* đang chạy đúng. Hướng dẫn khôi phục pad tĩnh
   > nằm ngay trong chú thích của file world.

4. **Áp overlay cho các package ngoài repo** (chỉ cần khi chạy pipeline M3.5):

   ```bash
   cp examples/SITL_PrecisionLanding/overlays/box_simulation/launch/box_spawn_only.launch.py \
      <đường-dẫn>/box_simulation/launch/
   ```

   Chi tiết: `overlays/README.md`.

---

## Yêu Cầu

Cần có:

- PX4 Gazebo simulation chạy được.
- PX4 `gz_x500_gimbal` chạy được.
- ROS 2 Humble.
- MAVROS cho các pipeline điều khiển hạ cánh chính xác.
- `ros_gz_image`, `cv_bridge`, `rqt_image_view`.
- ArUco C++ library có `libaruco.so.3.1`.

### Cách kiểm tra môi trường & cài đặt tự động (Khuyên dùng)

Để đảm bảo mọi thư viện (bao gồm `libaruco`, các package ROS 2, Python dependencies và Gazebo bridge thích hợp) đều được cài đặt chính xác, bạn chỉ cần chạy script kiểm tra tự động đi kèm trong thư mục dự án:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding
chmod +x verify_build_env.sh
./verify_build_env.sh
```

Script này sẽ tự động:
1. Phát hiện phiên bản Gazebo của bạn để cài đặt đúng gói bridge.
2. Kiểm tra và tự động cài các package ROS 2 còn thiếu.
3. Giải nén và tự động biên dịch thư viện C++ `libaruco 3.1.12` từ file đính kèm nếu hệ thống chưa có.
4. Cài đặt các package Python thông qua `requirements.txt`.

## Hoặc nếu bạn muốn tự cài đặt thủ công, hãy làm theo các bước dưới đây:

### Cài package ROS 2 thường dùng

Tùy thuộc vào phiên bản Gazebo được cài đặt trên máy của bạn (ví dụ: Gazebo Garden hoặc Gazebo Harmonic), chọn cài đặt các gói bridge tương thích:

**Với Gazebo Garden (Mặc định của PX4 v1.14+):**
```bash
sudo apt update
sudo apt install -y \
  ros-humble-ros-gz-image \
  ros-humble-ros-gz-bridge
```

**Với Gazebo Harmonic (Dành cho các hệ thống máy mới):**
```bash
sudo apt update
sudo apt install -y \
  ros-humble-ros-gzharmonic-image \
  ros-humble-ros-gzharmonic-bridge
```

**Cài đặt các gói ROS 2 bổ sung và MAVROS:**
```bash
sudo apt install -y \
  ros-humble-mavros \
  ros-humble-mavros-extras \
  ros-humble-cv-bridge \
  ros-humble-image-transport \
  ros-humble-rqt-image-view \
  python3-colcon-common-extensions \
  python3-opencv
```

**Cài đặt thư viện Python thông qua `requirements.txt`:**
```bash
pip3 install -r requirements.txt
```

> [!NOTE]
> **Khắc phục lỗi không tương thích OpenCV 4 (OpenCV 4.7+):**
> Trong file `aruco_standard_tracker_node.cpp`, hàm `cv::aruco::drawAxis` (đã bị xóa trên OpenCV mới) được cập nhật bằng `cv::drawFrameAxes` để đảm bảo code tự động biên dịch thành công trên mọi môi trường máy mới.


---

## Build

`px4_msgs` cần nằm trong workspace hoặc được source từ workspace khác:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash

# Nếu chưa có px4_msgs:
git clone https://github.com/PX4/px4_msgs.git src/px4_msgs

colcon build --symlink-install
source install/setup.bash
```

Nếu tracker thiếu `libaruco.so.3.1`, kiểm tra:

```bash
ldd install/aruco_fractal_tracker/lib/aruco_fractal_tracker/aruco_fractal_tracker | grep aruco
```

Nếu chưa resolve tới `/home/teedee/.local/lib/libaruco.so.3.1`, rebuild tracker:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon build --symlink-install --packages-select aruco_fractal_tracker --cmake-clean-cache
source install/setup.bash
```

---

## Dọn Tiến Trình Cũ

```bash
pkill -9 -f "gz sim|px4|mavros|tracker|lander|rqt_image_view|ros_gz"
```

---

## 1. Fractal ArUco Landing (MAVROS-based)

Pipeline định vị hạ cánh chính xác sử dụng MAVROS. Tracker C++ xuất contract `/landing/target_camera` (`dib_msgs/LandingTarget6D`) trong camera optical frame với state `LOST/SEARCHING/TRACKING`; topic pose `/aruco_fractal_tracker/poses` được giữ cho debug. Lander lọc target, bù camera offset, xoay theo yaw thân drone và điều khiển trong local ENU.

Cấu hình SITL hiện tại:

```text
box pose:     x=4.0, y=-3.5, z=0.0, yaw=0.0
marker:       0.50 m x 0.50 m, mounted on dib_box_landing_pad
camera:       1280 x 720, 30 Hz
horizontal FOV: 1.4137 rad (81°)
control loop: 30 Hz target, requirement >= 20 Hz
```
Kích thước vật lý thực tế của từng tầng:
Tầng ngoài cùng (Outer - Level 1): 50 cm (0.50 m)
Tầng giữa (Middle - Level 2): 12.5 cm (0.125 m)
Tầng trong cùng (Inner - Level 3): 3.125 cm (0.03125 m)

`dib_box_landing_pad/model.sdf`, `marker_size` trong launch và marker vật lý phải luôn dùng cùng kích thước. Detector sử dụng `custom_fractal.yml`; file này được sync sang PX4 cùng model.

* **Cập nhật file:**
  Ghi đè trực tiếp giá trị <horizontal_fov>1.4137</horizontal_fov> vào file
  ```bash
  /home/teedee/PX4/Tools/simulation/gz/models/gimbal/model.sdf trên đĩa.
  ```

* **Terminal 1: Khởi động PX4 SITL**

  ```bash
  cd ~/PX4
  PX4_GZ_WORLD=fractal_aruco_landing PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal
  ```

* **Terminal 2: Chạy MAVROS một lần và giữ nguyên**

```bash
source /opt/ros/humble/setup.bash
ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580
```

Kiểm tra MAVROS đã nối PX4:

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic echo --once /mavros/state
```

Kỳ vọng:

```text
connected: true
```

* **Terminal 3: Khởi động bridge camera, tracker và lander**

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch px4_offboard fractal_aruco_landing.launch.py
```

* **Terminal 4: Xem luồng camera có HUD overlay trực quan**

```bash
source /opt/ros/humble/setup.bash
ros2 run rqt_image_view rqt_image_view
```
*Chọn topic `/landing/annotated_image` từ thanh công cụ để theo dõi trực quan trạng thái FSM, tọa độ bám bắt, và các thông tin chẩn đoán trực tiếp.*



`fractal_aruco_landing.launch.py` không khởi động MAVROS. Khi cần sửa/restart tracker hoặc lander, chỉ restart Terminal 4. Không restart Terminal 2, như vậy PX4 vẫn nhận heartbeat mission computer từ MAVROS liên tục.

Nếu restart MAVROS trong lúc đang bay hoặc đang giữ OFFBOARD, QGroundControl/PX4 có thể báo:

```text
Critical: Connection to mission computer lost
```

Nếu PX4 checkout không nằm tại `~/PX4`, truyền đường dẫn cấu hình marker:

```bash
ros2 launch px4_offboard fractal_aruco_landing.launch.py \
  marker_configuration:=/absolute/path/to/custom_fractal.yml
```

Controller dùng ENU cho logic hạ cánh:

```text
search_x = East
search_y = North
pos_enu / target_enu / raw_enu / sp_enu đều là ENU
```

### 1.1 Box Hybrid Landing (SITL prototype)

Pipeline thử nghiệm cho flow `box_manager + precision landing` dùng cùng PX4 SITL, MAVROS và fractal tracker, nhưng thay lander cũ bằng FSM hybrid:

```text
IDLE -> DRONE_MISSION -> PRELANDING_CHECK -> WAIT_BOX_READY
     -> SEARCH -> HORIZONTAL_APPROACH -> DESCEND_OVER_TARGET
     -> LAND -> FLIGHT_IN_PROGRESS -> DONE
```

Trong prototype này, box thật được thay bằng `sim_box_manager`, publish `/sim_box/state`:

```text
IDLE -> PREPARING_FOR_LANDING -> WAITING_FOR_LANDING
```

Gazebo world đã có box tĩnh `dib_box_landing_pad` tại:

```text
x=4.0, y=-3.5, z=0.0, yaw=0.0
```

Trong Phase 2, vị trí này là fixture mô phỏng cho box/mission/marker. UAV nên bay tới vùng này bằng mission hoặc waypoint của box; hybrid lander chỉ bắt đầu visual refinement sau khi mission/prelanding đã hoàn tất, không dùng `search_x/search_y` để bay tới box.

Chạy PX4 SITL và MAVROS giống mục Fractal ArUco Landing ở trên. Terminal 3 đổi sang launch hybrid:

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/gimbal_simulation/ros2_ws/install/setup.bash
ros2 launch px4_offboard box_hybrid_landing.launch.py
```

Hybrid lander không tự khởi động mission và không tự bay OFFBOARD tới box trong state `DRONE_MISSION`. Hãy setup/khởi chạy mission bằng QGroundControl hoặc luồng mission thật, rồi gửi trigger để node bắt đầu monitor mission/box:

```bash
ros2 topic pub --once /box_hybrid_landing/trigger std_msgs/msg/String "data: 'land'"
```

Trong SITL, node dùng waypoint progress hoặc khoảng cách local tới box fixture `(4.0, -3.5)` để nhận biết đã tới vùng hạ cánh. `manual_drive_alt` mặc định là `10.0m`, đóng vai trò độ cao approach/visual acquire ban đầu. Chỉ sau đó nó mới chuẩn bị gimbal, gửi `REQUEST_LANDING` tới box và chuyển sang visual guidance.

Visual guidance mặc định dùng OFFBOARD setpoint sau khi đã tới box:

```bash
ros2 launch px4_offboard box_hybrid_landing.launch.py enable_offboard_visual_servo:=true
```

Kiểm tra FSM:

```bash
ros2 topic echo /box_hybrid_landing/state
ros2 topic echo /box_hybrid_landing/box_state
ros2 topic echo /box_hybrid_landing/comms
```

Yaw alignment hiện có guard:

```bash
ros2 launch px4_offboard box_hybrid_landing.launch.py enable_yaw_setpoint:=true yaw_gate_deg:=5.0
```

Chỉ bật sau khi đã xác nhận quyền điều khiển mode/setpoint không xung đột với PX4/MAVROS mission flow. Khi bật, yaw được align tại `final_alt` trong lúc giữ XY/altitude, rồi mới trigger `AUTO.LAND`. Có thể siết `yaw_gate_deg:=3.0` khi muốn test chính xác hơn.

---

## Giám Sát và Kiểm Tra

Quy trình nghiệm thu đầy đủ cho Fractal ArUco nằm ở:

```bash
~/PX4/examples/gimbal_simulation/docs/FLIGHT_TEST.md
```

FSM hiện tại của pipeline Fractal ArUco độc lập nằm ở:

```bash
~/PX4/examples/gimbal_simulation/docs/fractal_aruco_fsm.png
```

Proposal FSM cho hướng tích hợp mission-driven với `box_manager` nằm ở:

```bash
~/PX4/examples/gimbal_simulation/docs/main_fsm.mmd
~/PX4/examples/gimbal_simulation/docs/precision_landing_fsm.mmd
```

Kế hoạch mô phỏng SITL cho box-driven hybrid landing nằm ở:

```bash
~/PX4/examples/gimbal_simulation/docs/BOX_HYBRID_SITL_PLAN.md
```

* **Xem luồng camera có telemetry HUD**:
  ```bash
  source /opt/ros/humble/setup.bash
  ros2 run rqt_image_view rqt_image_view
  ```
  Chọn topic `/landing/annotated_image` để xem hình ảnh bám bắt mục tiêu trực quan cùng thông tin telemetry (FPS, FSM State, coordinates, TVEC).

* **Kiểm tra trạng thái FSM của Lander**:
  ```bash
  ros2 topic echo /lander/state
  ```

* **Kiểm tra tần số Setpoint gửi đến PX4**:
  ```bash
  ros2 topic hz /mavros/setpoint_position/local
  ```
  *(Timer điều khiển chạy 30Hz; kết quả đo nghiệm thu cần đạt >=20Hz khi đang ở chế độ Offboard.)*

---

## Kiểm Tra Nhanh

Camera bridge:

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /gimbal_camera
```

Tracker target và pose debug:

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic hz /landing/target_camera
ros2 topic echo --once /landing/target_camera
ros2 topic hz /aruco_fractal_tracker/poses
ros2 topic echo --once /aruco_fractal_tracker/poses
```

MAVROS topics:

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic hz /mavros/setpoint_position/local
ros2 topic echo --once /mavros/state
ros2 topic echo --once /mavros/extended_state
ros2 topic echo --once /mavros/local_position/pose
```

---

## Dấu Hiệu Thành Công

Landing thành công khi log có dạng:

```text
Marker detected
State: SEARCH -> HORIZONTAL_APPROACH
State: HORIZONTAL_APPROACH -> DESCEND_OVER_TARGET
Final altitude reached
PX4 land detector reports landed
LANDING COMPLETE
```

Không dùng force-disarm làm tiêu chuẩn thành công khi chạy thật.

---

## Ghi Chú

- Thống nhất kích thước tất cả các marker chính về `0.50m` (`marker_size:=0.50`).
- Nếu sau này đổi physical marker size trong `model.sdf`, phải đổi `marker_size` tương ứng trong file launch.
- `command 520 unsupported` là capability request MAVLink cũ từ client và không phải lệnh điều khiển landing.
- Trước một lần chạy sạch từ đầu, dừng các tiến trình PX4/MAVROS cũ để tránh giữ UDP endpoint hoặc quyền điều khiển gimbal từ phiên trước.
- Khi đang debug giữa chuyến bay hoặc đang giữ OFFBOARD, không restart MAVROS. Hãy giữ Terminal 2 chạy MAVROS riêng và chỉ restart Terminal 3 với `ros2 launch px4_offboard fractal_aruco_landing.launch.py`.

---

## 2. Hướng Dẫn Chạy Thực Tế & Mô Phỏng Với PX4 Precland

### 2.1. Chạy detect bằng cam thật:
```bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch siyi_camera_bridge real_fractal_detect.launch.py \
  enable_mavros:=false \
  rtsp_url:=rtsp://192.168.168.16:8554/main.264 \
  marker_configuration:=/home/teedee/PX4/examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/models/fractal_aruco_marker/custom_fractal.yml \
  marker_size:=0.162 \
  flip_180:=false
```

### 2.2. Chạy Precland điều khiển bằng PX4 (Sử dụng [qgc_sim_precland.launch.py](file:///home/teedee/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/px4_offboard/launch/qgc_sim_precland.launch.py) và [landing_target_bridge.py](file:///home/teedee/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/px4_offboard/px4_offboard/landing_target_bridge.py)):

#### Dọn Tiến Trình Cũ:
```bash
pkill -9 -f "gz sim|px4|mavros|tracker|lander|rqt_image_view|ros_gz"
```

#### Terminal 1: Khởi động PX4 SITL:
```bash
cd ~/PX4
PX4_GZ_WORLD=fractal_aruco_landing PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal
```

#### Terminal 2: Chạy MAVROS một lần và giữ nguyên:
```bash
source /opt/ros/humble/setup.bash
ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580
```
Kiểm tra MAVROS đã nối PX4:
```bash
source /opt/ros/humble/setup.bash
source ~/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic echo --once /mavros/state
```
Kỳ vọng:
```text
connected: true
```

#### Terminal 3: Khởi động bridge camera, tracker và lander:
```bash
source /opt/ros/humble/setup.bash
source ~/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch px4_offboard qgc_sim_precland.launch.py
```

#### Terminal 4: Xem luồng camera có HUD overlay trực quan:
```bash
source /opt/ros/humble/setup.bash
ros2 run rqt_image_view rqt_image_view
```
*Chọn topic `/landing/annotated_image` từ thanh công cụ để theo dõi trực quan trạng thái FSM, tọa độ bám bắt, và các thông tin chẩn đoán trực tiếp.*

`qgc_sim_precland.launch.py` không khởi động MAVROS. Khi cần sửa/restart tracker hoặc lander, chỉ restart Terminal 3. Không restart Terminal 2, như vậy PX4 vẫn nhận heartbeat mission computer từ MAVROS liên tục.

### 2.3. Hướng Dẫn Chạy Precland Điều Khiển Bằng PX4 Chế Độ Offboard:
Sử dụng [qgc_offboard_precland.launch.py](file:///home/teedee/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/px4_offboard/launch/qgc_offboard_precland.launch.py) và [offboard_precland_controller.py](file:///home/teedee/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/px4_offboard/px4_offboard/offboard_precland_controller.py):

#### Dọn Tiến Trình Cũ:
```bash
pkill -9 -f "gz sim|px4|mavros|tracker|lander|rqt_image_view|ros_gz"
```

#### Terminal 1: Khởi động PX4 SITL:
```bash
cd ~/PX4
PX4_GZ_WORLD=fractal_aruco_landing PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal
```

#### Terminal 2: Chạy MAVROS một lần và giữ nguyên:
```bash
source /opt/ros/humble/setup.bash
ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580
```
Kiểm tra MAVROS đã nối PX4:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic echo --once /mavros/state
```
Kỳ vọng:
```text
connected: true
```

#### Terminal 3: Khởi động bridge camera, tracker và lander:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch px4_offboard qgc_offboard_precland.launch.py
```

#### Terminal 4: Xem luồng camera có HUD overlay trực quan:
```bash
source /opt/ros/humble/setup.bash
ros2 run rqt_image_view rqt_image_view
```
*Chọn topic `/landing/annotated_image` từ thanh công cụ để theo dõi trực quan trạng thái FSM, tọa độ bám bắt, và các thông tin chẩn đoán trực tiếp.*

`qgc_offboard_precland.launch.py` không khởi động MAVROS. Khi cần sửa/restart tracker hoặc lander, chỉ restart Terminal 3. Không restart Terminal 2, như vậy PX4 vẫn nhận heartbeat mission computer từ MAVROS liên tục.

### 2.4. Hướng Dẫn Chạy SITL Precland sử dụng pkg precision_landing (Phiên bản C++):
> **Lưu ý**: `dib_msgs` chỉ thêm `LandingTarget6D` so với bản dev.

#### Dọn Tiến Trình Cũ:
```bash
pkill -9 -f "gz sim|px4|mavros|tracker|lander|rqt_image_view|ros_gz"
```

#### Terminal 1: Khởi động PX4 SITL:
```bash
cd ~/PX4
PX4_GZ_WORLD=fractal_aruco_landing PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal
```

#### Terminal 2: Chạy MAVROS một lần và giữ nguyên:
```bash
source /opt/ros/humble/setup.bash
ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580
```
Kiểm tra MAVROS đã nối PX4:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic echo --once /mavros/state
```
Kỳ vọng:
```text
connected: true
```

#### Terminal 3: Khởi động bridge camera, tracker và lander:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 launch precision_landing sitl_precland.launch.py
```

#### Terminal 4: Xem luồng camera có HUD overlay trực quan:
```bash
source /opt/ros/humble/setup.bash
ros2 run rqt_image_view rqt_image_view
```
Chọn topic `/landing/annotated_image` từ thanh công cụ để theo dõi trực quan trạng thái FSM, tọa độ bám bắt, và các thông tin chẩn đoán trực tiếp.

`sitl_precland.launch.py` không khởi động MAVROS. Khi cần sửa/restart tracker hoặc lander, chỉ restart Terminal 3. Không restart Terminal 2, như vậy PX4 vẫn nhận heartbeat mission computer từ MAVROS liên tục.

#### Gửi bài bay tự động qua service:

*   **Terminal 5**:
    ```bash
    source ~/test_req/install/setup.bash 
    ros2 launch ros2_telemetry plan_upload.launch.py drone_id:=d1
    ```

*   **Terminal 6**:
    ```bash
    source ~/test_req/install/setup.bash 
    ros2 service call /d1/mission_upload dib_msgs/srv/MissionUpload "{mission: [
      {command: 22, param1: 0.0, param2: 0.0,  latitude: 47.397929, longitude: 8.546217, altitude: 15.0},
      {command: 16, param1: 5.0, param2: 0.0, latitude: 47.39797, longitude: 8.546322, altitude: 15.0}, 
      {command: 16, param1: 5.0, param2: 0.0, latitude: 47.3979298, longitude: 8.546217, altitude: 15.0},
      {command: 23, param1: 0.0, param2: 0.0, latitude: 47.3979298, longitude: 8.546217, altitude: 0.0} 
    ]}"
    ```

---

## 3.0. Hướng Dẫn Chạy Test Trên Camera Thật (Real Camera RTSP)

Để kiểm tra trực tiếp khả năng nhận diện Aruco Fractal của camera vật lý (SIYI A8 Mini hoặc bất kỳ camera IP nào) mà chưa cần chạy mô phỏng hay nối với Pixhawk, sử dụng launch file độc lập sau:

#### Terminal 1: Khởi động Camera Publisher và Aruco Tracker
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash

# Tham số enable_mavros:=false dùng để chạy khi chưa có kết nối mạch FCU
ros2 launch precision_landing real_fractal_detect.launch.py enable_mavros:=false
```

*Lưu ý: Nếu bạn muốn thay đổi địa chỉ RTSP hoặc thông số camera calibration (tiêu cự fx, fy, cx, cy), hãy chỉnh sửa tại file `~/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/precision_landing/config/rtsp_publisher_params.yaml`.*

#### Terminal 2: Theo dõi luồng ảnh Debug
Bạn mở rqt để xem luồng video từ camera kèm theo khung bounding box nhận diện marker (nếu có):
```bash
source /opt/ros/humble/setup.bash
ros2 run rqt_image_view rqt_image_view
```
*Chọn topic `/siyi/fractal_debug` trên thanh công cụ của RQT.*

Nếu bạn muốn kiểm tra luồng tọa độ (pose) nhận diện liên tục:
```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
ros2 topic echo /siyi/fractal_pose
```

---

## 4. Drone-in-a-Box — Pipeline Đầy Đủ (M3.5 + M3.6)

Toàn bộ hệ thống trong **một world Gazebo duy nhất**: drone `x500_gimbal` bắt
tay với box qua service `dib_msgs`, box thật (khớp nắp + kẹp, điều khiển bằng
ros2_control) mở nắp đón, drone hạ cánh bằng thị giác xuống marker fractal nằm
trên sàn box, box kẹp giữ drone, drone xin tắt nguồn, và box chuyển sang sạc —
vòng đời `EMPTY → … → CHARGING` khép trọn.

```
box_manager  ──service──▶  box_hardware_adapter  ──JointTrajectory──▶  ros2_control
     ▲                                                                      │
     └──────────────  /joint_states  ◀──────────  Gazebo (cùng world)  ◀─────┘
                                                        │
drone: MAVROS ──▶ mavros_to_dib_telemetry ──▶ box_manager
       camera ──▶ aruco_fractal_tracker ──▶ offboard_precland_controller ──▶ MAVROS
```

### 4.1. Thành phần

| Package | Vai trò |
|---|---|
| `precision_landing` | Tracker fractal + `offboard_precland_controller` (FSM hạ cánh, C++) + `mavros_to_dib_telemetry` |
| `box_manager` | FSM của box (`EMPTY → PREPARING_FOR_LANDING → WAITING_FOR_LANDING → SECURING_DRONE`) |
| `box_hardware_adapter` | Dịch service của `box_manager` thành `JointTrajectory` cho ros2_control, và dịch `/joint_states` ngược lại thành `/lid/status`, `/clamp/status` |
| `box_simulation` | Model box khớp động (nắp, 2 cặp kẹp) |
| `dib_box_marker` | Marker fractal 0.50 m đặt trên sàn box |

Ba launch file dùng để chạy, tất cả nằm trong `precision_landing`:

| Launch | Khởi động gì |
|---|---|
| `sitl_precland.launch.py` | gz bridge + tracker + `offboard_precland_controller` |
| `sitl_mavros.launch.py` | MAVROS **có `use_sim_time`** (xem 4.6) |
| `dib_bringup.launch.py` | adapter + FSM box + cầu telemetry + fixture GPS |

### 4.2. Chuẩn bị

Yêu cầu build từ nguồn của `gz_ros2_control` cho **Gazebo Harmonic**. Bản apt
`ros-humble-gz-ros2-control` build cho **Fortress** và sẽ làm gz server
**segfault** khi spawn box (plugin system Harmonic nạp plugin hardware Fortress
qua pluginlib → truyền `v8::EntityComponentManager` vào hàm nhận `v6::`).

```bash
# Kiểm tra: nếu còn bản apt thì gỡ đi cho chắc
apt-cache rdepends --installed ros-humble-gz-ros2-control   # phải RỖNG
sudo apt remove ros-humble-gz-ros2-control
```

### 4.3. Dọn tiến trình cũ

Bỏ qua bước này là nguyên nhân phổ biến nhất khiến máy lag và lần chạy sau
hỏng theo kiểu khó hiểu.

```bash
pkill -f 'px4|gz sim|gzserver|ruby.*gz|robot_state_publisher|spawner|controller_manager'
pkill -f 'mavros|offboard_precland|aruco_fractal|box_state_manager'
sleep 2
pgrep -af 'px4|gz sim' || echo "sach"
```

### 4.4. Header cho MỌI terminal

```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

### 4.5. Giai đoạn A — dựng world và kiểm box/marker (2 terminal)

Chạy riêng giai đoạn này trước. Nếu marker không hiện thì cả pipeline chắc chắn
thất bại, mà giai đoạn A chỉ tốn 2 tiến trình thay vì 9.

**Terminal 1 — PX4 + Gazebo:**
```bash
export GZ_SIM_RESOURCE_PATH=$HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share
cd ~/PX4 && PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing
```

> **Hai biến này bắt buộc ở Terminal 1, không phải ở đâu khác.**
>
> - `GZ_SIM_RESOURCE_PATH` — tiến trình phân giải `model://` là **gz server**,
>   do PX4 khởi động. Đặt biến này trong launch file spawn **không có tác
>   dụng**: `SetEnvironmentVariable` chỉ áp cho tiến trình con của launch đó.
>   Thiếu nó thì box spawn thành công về mặt vật lý (có trong `gz model --list`,
>   controller nạp đủ, `/joint_states` chạy) nhưng **mọi `<visual>` đều rỗng** —
>   một cái box vô hình, rất dễ đọc nhầm thành "spawn hỏng".
>   PX4 **nối thêm** chứ không ghi đè biến này, nên export trước là an toàn.
> - `PX4_GZ_NO_FOLLOW=1` — bỏ khoá camera Gazebo theo drone, để xoay đi nhìn
>   box. Đang chạy rồi mà quên thì:
>   `gz topic -t /gui/track -m gz.msgs.CameraTrack -p "track_mode: NONE"`
>   (`PX4_NO_FOLLOW` không tồn tại; `PX4_NO_FOLLOW_MODE` chỉ dành cho
>   gazebo-classic.)

Đợi tới khi thấy dấu nhắc `pxh>` rồi mới sang Terminal 2.

**Terminal 2 — spawn box + marker vào chính world đó:**
```bash
ros2 launch box_simulation box_spawn_only.launch.py
```

Launch chờ **20 giây** sau khi spawn xong rồi mới nạp 4 controller. Đây là cố ý:
`controller_manager` nằm trong plugin gz và chỉ khởi động khi box được spawn;
gọi `load_controller` ngay lúc đó bắt gặp nó đang khởi tạo và phản hồi mất
~15 s, trong khi cả `ros2 control load_controller` lẫn `spawner` đều
hard-code timeout **10 s** cho lời gọi service ở Humble. Mỗi controller cũng
chạy một tiến trình `spawner` riêng, để một cái lỗi không chặn ba cái còn lại.

**Kiểm (sau Terminal 2 khoảng 40 giây):**
```bash
gz model --list                       # có Box và dib_box_marker
gz model -m Box -p                    # [2.5 -2.0 0.78233] [1.5708 0 0]
ros2 control list_controllers         # 4 dòng, tất cả 'active'
ros2 topic echo --once /joint_states  # 6 joint
```

Controller nào còn `unconfigured` thì nó **đã nạp**, chỉ mất nửa sau do timeout.
Hoàn tất bằng tay, **hai bước** (`unconfigured → active` không phải chuyển
trạng thái hợp lệ):
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

> Dùng `-r 2 -t 6`, **không dùng `--once`**: `--once` hủy publisher ngay khi vừa
> gửi, thường là trước khi controller kịp discovery xong, và message rơi mất
> trong im lặng.

Nhìn vào lòng box: phải thấy ô marker fractal đen-trắng trên mặt sàn.

### 4.6. Giai đoạn B — vòng kín (thêm 3 terminal)

Giữ nguyên Terminal 1 và 2. Tổng cộng **5 terminal**, không phải 9: bốn node
phía box đã gom vào một launch.

| T | Lệnh | Vai trò |
|---|---|---|
| 3 | `ros2 launch precision_landing sitl_precland.launch.py` | bridge + tracker + controller |
| 4 | `ros2 launch precision_landing sitl_mavros.launch.py` | MAVROS (đồng hồ mô phỏng) |
| 5 | `ros2 launch precision_landing dib_bringup.launch.py` | **cả 4 node phía box trong một terminal** |

`dib_bringup.launch.py` gom `box_hardware_adapter_node`, `box_state_manager_node`,
`mavros_to_dib_telemetry` và fixture GPS. Không cần thứ tự khởi động: service
được chờ kiểu lazy, mọi subscription đều fire-and-forget.

```bash
# tắt fixture GPS khi chạy trên phần cứng thật (box có GPS thật)
ros2 launch precision_landing dib_bringup.launch.py use_gps_fixture:=false
```

Giám sát (mở khi cần, không phải lúc nào cũng cần):
```bash
ros2 run rqt_image_view rqt_image_view /precision_landing/debug_image
ros2 topic echo --field data /landing/pose_sync_ms     # ms; -1 = lệch đồng hồ
```

> **Terminal 4 dùng `sitl_mavros.launch.py`, KHÔNG dùng `mavros px4.launch`.**
> `px4.launch` không khai báo argument `use_sim_time`, nên truyền
> `use_sim_time:=true` vào nó bị **bỏ qua trong im lặng**: MAVROS chạy đồng hồ
> tường trong khi ảnh camera mang dấu thời gian mô phỏng. Tracker phát hiện
> được và vẽ đỏ `sync N/A: clock mismatch` — khi đó độ cao in trên HUD là pose
> mới nhất, không phải pose ứng với khung hình đang xem.
> Kiểm nhanh sau khi khởi động: `ros2 param get /mavros use_sim_time` → `True`.

**Kiểm 3 thứ trước khi bay** — làm lúc này tốn 10 giây, phát hiện sau khi bay
tốn cả một lượt chạy:

```bash
# 1. Đồng bộ đồng hồ — tiêu chí THẬT, đo trực tiếp trên dữ liệu
ros2 topic echo --once --field data /landing/pose_sync_ms   # số dương (vd 40.0), KHÔNG phải -1.0

# 2. MAVROS dùng đồng hồ mô phỏng
ros2 param get /mavros/mavros_node use_sim_time             # Boolean value is: True

# 3. Bốn controller của box
ros2 control list_controllers                               # 4 dòng, tất cả 'active'
```

> **Node là `/mavros/mavros_node`, không phải `/mavros`.** MAVROS chạy dưới
> namespace `mavros` và tách thành hàng chục node plugin
> (`/mavros/local_position`, `/mavros/imu`, …); `/mavros` tự nó không tồn tại và
> `ros2 param get /mavros ...` trả về `Node not found` — đó là sai tên node, chứ
> không phải MAVROS hỏng.
>
> Trong ba lệnh trên thì **lệnh 1 mới là bằng chứng**: nó đo độ lệch thật giữa
> dấu thời gian ảnh và pose. Lệnh 2 chỉ xác nhận nguyên nhân.

Bay, trong `pxh>` của Terminal 1:
```
pxh> commander takeoff
pxh> commander land
```
`offboard_precland_controller` bắt được `AUTO.LAND`, tự chuyển sang `OFFBOARD`
và bắt đầu chuỗi `GOTO_BOX → PRELANDING_CHECK → WAIT_BOX_READY → START`.

**Thấy FSM đứng ở `IDLE` khi chưa chạy MAVROS là ĐÚNG**, không phải hỏng:
controller chỉ rời `IDLE` khi MAVROS báo drone đang bay.

### 4.7. Ba cấu hình sai là hỏng cả lần chạy

**1. `box_id` phải khớp giữa hai file.** `box_state_manager.yaml` dùng
`box_id: 2`, nên `offboard_precland_params.yaml` cũng phải là `2`. Lệch nhau thì
drone gọi `b1/cmd` (không tồn tại) và chờ `/b1/telemetry` (không ai publish) →
`box_telemetry_valid_` mãi false → FSM **bỏ qua toàn bộ phần bắt tay** mà không
báo lỗi nào. Xác nhận bằng log khởi động:
```
Derived box_telemetry_topic='/b2/telemetry' from box_id=2
BoxLink: box_id=2 drone_id=1, cmd service 'b2/cmd', agent_id=12
```

**2. Box phải có toạ độ GPS.** `box_state_manager` lấy vị trí box từ topic
`gps` (`sensor_msgs/NavSatFix`). Trong SITL **không ai publish topic này** —
sensor `navsat` của `box_simulation` chưa có `ros_gz_bridge`. Hậu quả:
`box_info.latitude/longitude` bằng 0, `st_goto_box()` tính setpoint cách hàng
nghìn km và drone bay đi mất. Cần một node publish `/gps` tại đúng vị trí
marker, ENU `(2.5129, −2.5896)` trong `fractal_aruco_landing`:
```
lat = 47.397947795   lon = 8.546197088
```

**3. `marker_size` phải khớp kích thước plane thật.** `marker.png` có viền
trắng rộng 1 module, nên marker **đen** chỉ chiếm 80.12% cạnh ảnh. Muốn marker
đen đúng 0.50 m (giá trị `marker_size` trong `offboard_precland_params.yaml`)
thì plane phải là `0.50 / 0.8012 = 0.6241 m`. Đổi một số thì phải đổi số kia,
nếu không pose sẽ sai **thang đo** → sai độ cao → flare sớm hoặc cắm xuống.

### 4.8. Dấu hiệu chạy đúng

FSM drone và box đan xen nhau theo đúng quan hệ nhân quả:
```
DRONE  -> GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY
BOX    -> PREPARING_FOR_LANDING(6) -> WAITING_FOR_LANDING(7)
DRONE  -> START -> HORIZONTAL_APPROACH -> DESCEND_ABOVE_TARGET -> FINAL_APPROACH
MAVROS -> landed_state=ON_GROUND
BOX    -> SECURING_DRONE(8)
```
- Box chỉ rời `EMPTY` **sau** khi drone vào `WAIT_BOX_READY` → chính
  `REQUEST_LANDING` của drone gây ra.
- Drone chỉ vào `START` **sau** khi box báo `WAITING_FOR_LANDING` → không chạy
  trước nắp box.
- **Không có** `SEARCH` kéo dài và **không có** `FALLBACK`.

Adapter điều khiển đúng cơ cấu box:
```
/lid/cmd   command=1 -> lid target 1.570 rad     (mở nắp đón drone)
/clamp/cmd select=1 h_cmd=200 -> h=0.200 m       (kẹp ngang, sau khi đáp)
/clamp/cmd select=2 v_cmd=200 -> v=0.200 m       (kẹp dọc)
/lid/cmd   command=0 -> lid target 0.000 rad     (đóng nắp)
```

Vòng đời khép trọn tới `CHARGING` — **sau khi drone chạm đất còn khoảng 35-40
giây nữa**, đừng tắt sớm:
```
offboard_precland: LANDING COMPLETE — disarmed. Waiting for box to secure and charge.
box_state_manager: Box in SECURING_DRONE state, securing state: 5   (kẹp + đóng nắp)
offboard_precland: BoxLink: sending TURN_OFF_DRONE to b2 (agent_id=12)
box_hardware_adapter: /dock/power_button/cmd command=0 -> drone power OFF
mavros_to_dib_telemetry: Dock power OFF: stopping publishing d1/telemetry
box_state_manager: Box in CHARGING state
offboard_precland: Box reached CHARGING — drone-in-a-box cycle complete
```
`TURN_OFF_DRONE` được gửi lặp lại mỗi 3 giây là **đúng thiết kế**: lệnh
idempotent, box giữ nó như một cờ dính và chỉ tiêu thụ khi kẹp/nắp đã đóng xong.

> **Vì sao phải giả lập cú cắt điện.** `box_manager` rời `POWER_OFF` sang `DONE`
> (rồi mới `CHARGING`) khi telemetry drone **im lặng quá 5 giây**
> (`securing_state_manager.cpp:217-220`). Trên phần cứng thật, box cắt nguồn
> nên máy tính đồng hành tắt và sự im lặng đó là miễn phí. Trong SITL, MAVROS
> chạy mãi, nên `box_hardware_adapter` publish `/dock/drone_power` và
> `mavros_to_dib_telemetry` ngừng phát khi nhận `false`. Thiếu mắt xích này thì
> box kẹt ở `POWER_OFF` vĩnh viễn — drone vẫn hạ cánh và bị kẹp đúng, nhưng
> vòng đời không bao giờ khép.

### Đọc số latency cho đúng (quan trọng khi chạy HITL)

`E2E latency (image -> debug)` được tính là `now() − image_stamp`. Phép trừ đó
**chỉ là độ trễ khi hai đầu dùng chung một đồng hồ**. Nếu camera đóng dấu thời
gian bằng đồng hồ riêng, hoặc NTP giữa camera và máy tính nhúng lệch nhau, thì
cùng phép trừ ấy cho ra **độ lệch đồng hồ** — và nó trông y hệt một độ trễ khổng
lồ. Đây chính là lý do các lần chạy HITL báo e2e latency rất lớn trên máy nhúng
trong khi `Detector processing` (đo bằng `steady_clock`, miễn nhiễm với lệch
đồng hồ) chỉ vài mili giây.

Phân biệt bằng **hình dạng**, không phải độ lớn:

| | sàn (floor) | dao động (jitter) |
|---|---|---|
| Độ trễ thật | nhỏ | thấy rõ, thay đổi từng khung |
| Lệch đồng hồ | lớn | gần như bằng 0 |

Tracker theo dõi sàn trượt 10 giây và tự gắn cờ:
```
E2E latency (image -> debug): 2480.0 ms  [CLOCK OFFSET? floor=2478 jitter=2]
```
Kèm cảnh báo trong log, giãn 10 giây một lần. Thấy cờ này thì **đừng đi tối ưu
hiệu năng** — hãy đồng bộ thời gian giữa camera và máy tính trước.

Cửa sổ chấp nhận cũng đã siết từ **60 giây** xuống **2 giây**. Ngưỡng cũ không
phải là kiểm tra tính hợp lý: mọi độ lệch dưới một phút đều lọt qua và được hiển
thị như latency.

**Đọc HUD cho đúng.** `UAV ENU U` và `MARKER DIST` **không bằng nhau**, và đó là
đúng: `U` là độ cao so với **điểm cất cánh**, còn marker giờ nằm **trên nóc box,
cao 0.64 m**. Kỳ vọng `U ≈ MARKER DIST + 0.64`. Trước M3.5 marker nằm bẹp dưới
đất nên hai số trùng nhau — bản ghi cũ vì thế gây hiểu nhầm. Số so được với
`MARKER DIST` là `alt` trong dòng `DESCEND` của controller (`pos_enu_.z` trừ cao
độ pad), không phải `alt` trong dòng `[YAW-3D]` (`pos_enu_.z` thô).

Kết quả tham chiếu của lần chạy đạt: **sai số hạ cánh 4.0 cm**
(`final_xy=(2.54, −2.56)` so với marker `(2.5129, −2.5896)`), độ cao lúc chạm
`0.602–0.628 m` khớp cao độ sàn box `0.63673 m`.

Dòng `Ground contact: blocked by 20.5cm → force-disarm` **không phải lỗi**:
drone dừng cao hơn mặt đất 0.6 m vì nó đang đứng trên box, và nhánh
force-disarm xử lý đúng tình huống đó.

Marker fractal tự rụng tầng theo độ cao, đúng thiết kế — `ids=[0,1,2]` ở trên
cao, `ids=[1,2]` khi xuống ~0.65 m (tầng ngoài 0.50 m ra khỏi khung hình, hai
tầng trong 0.125 m và 0.031 m tiếp quản).

### 4.9. Chỉnh hướng đậu của drone (`marker_yaw`)

Tracker suy ra một góc yaw từ marker và controller khoá drone vào góc đó — nên
**xoay marker là xoay hướng drone đậu**.

Mặc định `marker_yaw = 1.5708` (90°). Đổi được ngay trên dòng lệnh, **chỉ cần
khởi động lại Terminal 2, không phải khởi động lại PX4**:

```bash
ros2 launch box_simulation box_spawn_only.launch.py marker_yaw:=1.5708
```

Thử `0.0` / `1.5708` / `3.1416` / `-1.5708`, giữ giá trị nào đậu drone thẳng
hàng giữa hai cặp kẹp.

> Tiêu chí là **hai cặp kẹp**, không phải màu nắp. Kẹp đóng theo world Y (cách
> nhau 0.774 m) và world X (0.782 m), nên thân drone phải nằm dọc theo hai trục
> đó. Ở `marker_yaw = 0` hệ marker trùng world ENU, drone đậu ở heading 0
> (hướng Đông) và chúc mũi vào nắp — nhìn thì biết là sai, nhưng chọn theo mắt
> nhìn nắp vẫn có thể lệch 90° so với kẹp.

### 4.10. Giới hạn đã biết

`box_manager` dừng ở `SECURING_DRONE`, securing state 5, lặp
`Waiting for drone to request power off`. Chuỗi kẹp/nắp đã hoàn tất; box chờ
drone gọi tiếp để sang `CHARGING`, nhưng phía drone **chưa có** bước yêu cầu
power-off sau khi disarm. Đây là phần còn thiếu của vòng đời đầy đủ, chưa được
triển khai.

`box_simulation` chưa có `ros_gz_bridge` cho sensor `navsat`, nên vẫn phải dùng
node fixture publish `/gps` (mục 4.7).
