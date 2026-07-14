# Test Fractal Tracker Với Camera Thật

README này hướng dẫn người mới test Fractal ArUco tracker với camera thật SIYI A8 Mini trong workspace:

```text
~/PX4/examples/SITL_PrecisionLanding/ros2_ws
```

Mục tiêu của bài test:

- Lấy video RTSP từ SIYI camera.
- Publish ảnh ROS 2 trên `/siyi/image_raw`.
- Publish calibration trên `/siyi/camera_info`.
- Chạy Fractal ArUco tracker.
- Xem ảnh debug trên `/siyi/fractal_debug`.
- Kiểm tra pose marker trên `/siyi/fractal_pose`.

## Pipeline

```text
SIYI RTSP camera
  -> precision_landing/rtsp_publisher
  -> /siyi/image_raw + /siyi/camera_info
  -> precision_landing/aruco_fractal_tracker
  -> /siyi/fractal_debug
  -> /siyi/fractal_pose
  -> /siyi/landing_target
```

Launch khuyên dùng để test camera thật:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py enable_mavros:=false
```

## File Quan Trọng

Camera RTSP và calibration:

```text
~/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/precision_landing/config/rtsp_publisher_params.yaml
```

Giá trị hiện tại:

```yaml
siyi_rtsp_publisher:
  ros__parameters:
    rtsp_url: "rtsp://192.168.168.16:8554/main.264"
    frame_id: "siyi_camera_optical_frame"
    flip_180: false
    target_fps: 30.0

    image_width: 1280
    image_height: 720

    camera_fx: 733.95577
    camera_fy: 735.28401
    camera_cx: 654.37518
    camera_cy: 352.23005

    camera_d: [-0.119821, 0.087530, -0.007342, -0.002788, 0.0]
```

Fractal marker config:

```text
~/PX4/examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/models/fractal_aruco_marker/custom_fractal.yml
```

Ảnh marker để in ra:

```text
~/PX4/examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/models/fractal_aruco_marker/marker.png
```

## 1. Chuẩn Bị Trước Khi Chạy

Kết nối máy tính với Wi-Fi/ethernet của SIYI camera, sau đó kiểm tra camera có ping được không:

```bash
ping 192.168.168.16
```

Nếu RTSP IP của camera khác, sửa dòng này trong file config:

```yaml
rtsp_url: "rtsp://<camera-ip>:8554/main.264"
```

Kiểm tra marker thật:

- In đúng ảnh `marker.png`.
- Đặt marker phẳng, sáng rõ, không bị che góc.
- `marker_size` trong launch phải bằng kích thước cạnh ngoài cùng của marker thật.
- Mặc định repo đang dùng `marker_size:=0.50`, tức marker ngoài cùng 50 cm.

## 2. Build Workspace

Nếu đây là lần đầu build workspace, build tất cả package:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Sau này, nếu chỉ sửa camera config/launch và muốn build nhanh lại các package liên quan:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select precision_landing siyi_camera_bridge
source install/setup.bash
```

Mỗi terminal mới đều cần source:

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

## 3. Chạy Test Camera + Tracker, Không MAVROS

Dùng lệnh này khi chỉ muốn test detection ngoài đời thực, chưa cần cắm Pixhawk:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch precision_landing real_fractal_detect.launch.py enable_mavros:=false
```

Nếu marker thật không phải 50 cm, truyền kích thước đúng. Ví dụ marker 16.2 cm:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.162
```

Nếu PX4 checkout không nằm ở `~/PX4`, truyền đường dẫn tuyệt đối tới `custom_fractal.yml`:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_configuration:=/absolute/path/to/custom_fractal.yml
```

## 4. Xem Ảnh Camera Và Debug

Mở terminal mới, source workspace:

```bash
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
```

Xem ảnh raw từ camera:

```bash
ros2 run rqt_image_view rqt_image_view
```

Chọn topic:

```text
/siyi/image_raw
```

Xem ảnh debug của tracker:

```bash
ros2 run rqt_image_view rqt_image_view
```

Chọn topic:

```text
/siyi/fractal_debug
```

Nếu tracker bắt được marker, ảnh debug sẽ có overlay/khung detect và log terminal sẽ có pose/tracking.

## 5. Kiểm Tra Topic

Kiểm tra camera có publish ảnh:

```bash
ros2 topic hz /siyi/image_raw
```

Kiểm tra camera calibration:

```bash
ros2 topic echo /siyi/camera_info --once
```

Trong message, `k` và `d` nên khớp với file config:

```text
k: [733.95577, 0.0, 654.37518, 0.0, 735.28401, 352.23005, 0.0, 0.0, 1.0]
d: [-0.119821, 0.08753, -0.007342, -0.002788, 0.0]
```

Kiểm tra pose marker:

```bash
ros2 topic echo /siyi/fractal_pose
```

Kiểm tra output cho landing controller:

```bash
ros2 topic echo /siyi/landing_target
```

Kiểm tra node đang chạy:

```bash
ros2 node list
```

Kỳ vọng thấy:

```text
/siyi_rtsp_publisher
/aruco_fractal_tracker
```

## 6. Ghi Data Ra CSV Khi Đo Xa

Khi đo ngoài đời thực, bạn có thể khó nhìn màn hình từ xa. Repo có node logger:

```text
precision_landing/fractal_tracking_csv_logger
```

Node này subscribe `/siyi/landing_target` và ghi file CSV vào:

```text
~/PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs
```

CSV sẽ có các cột quan trọng:

- `config`: mã cấu hình test, ví dụ `A1`, `A2`, `B1`.
- `resolution`: độ phân giải test, ví dụ `640x480`, `1280x720`.
- `tag_size_cm`: kích thước cạnh ngoài cùng của marker/tag.
- `test_distance_m`: khoảng cách danh nghĩa nếu bạn đang test một mốc cố định.
- `cpu_percent`: %CPU toàn hệ thống tại thời điểm log.
- `gpu_percent`: %GPU từ `nvidia-smi`, nếu máy có NVIDIA GPU.
- `fps`: tốc độ message `/siyi/landing_target` trong cửa sổ gần nhất.
- `detection_rate_percent`: tỷ lệ frame đang `TRACKING` trong cửa sổ gần nhất.
- `accuracy_percent`: độ chính xác tương đối so với khoảng cách thật bạn nhập.
- `e2e_latency_ms`: độ trễ từ timestamp ảnh tới lúc logger nhận target message.
- `notes`: ghi chú tự do.
- `state_name`: trạng thái tracker, cần ưu tiên dòng `TRACKING`.
- `x_m`, `y_m`, `z_m`: tọa độ marker trong camera frame.
- `distance_cm`: khoảng cách tracker đo được, tính bằng `sqrt(x^2 + y^2 + z^2)`.
- `expected_distance_cm`: khoảng cách thật nếu bạn nhập vào. Nếu đo liên tục thì có thể để `0`.
- `error_cm`: sai số `distance_cm - expected_distance_cm`, chỉ có ý nghĩa khi bạn nhập khoảng cách thật.

Lưu ý rất quan trọng:

- `marker_size:=0.162` là kích thước cạnh ngoài cùng của marker thật, tức 16.2 cm.
- `distance_cm` trong file CSV là khoảng cách tracker đo được tại từng thời điểm.
- `logger_expected_distance_cm:=70` chỉ dùng khi bạn muốn ghi thêm khoảng cách thật 70 cm để tính sai số.
- Hai giá trị này khác nhau, không dùng lẫn cho nhau.
- Nếu đo continuous và không truyền `logger_test_distance_m`, cột `test_distance_m` sẽ tự dùng khoảng cách tracker đo được khi đang `TRACKING`.
- Nếu không có `nvidia-smi`, `gpu_percent` sẽ là `N/A`; có thể truyền `logger_gpu_percent_override:=...` nếu bạn đo GPU bằng công cụ khác.
- Nếu không truyền `logger_expected_distance_cm`, `accuracy_percent` sẽ là `N/A` vì logger không biết khoảng cách thật để tính sai số.

Ví dụ về accuracy/sai số:

- Nếu đặt marker thật ở 1 m, truyền `logger_expected_distance_cm:=100`.
- Nếu tracker đo `distance_cm=103`, thì `error_cm=+3`.
- Nếu tracker đo `distance_cm=97`, thì `error_cm=-3`.
- `accuracy_percent` là cách quy đổi tương đối từ sai số đó. Với test thực tế, bạn nên nhìn cả `error_cm` vì nó dễ hiểu hơn: 1 m sai số `+3 cm`, 2 m sai số `-5 cm`, v.v.

### Xem latency trực quan

Tracker đã vẽ latency trực tiếp lên ảnh debug. Mở app xem ảnh:

```bash
ros2 run rqt_image_view rqt_image_view
```

Chọn topic:

```text
/siyi/fractal_debug
```

Ở panel dưới bên trái sẽ có:

- `E2E latency (image -> debug)`: gần đúng độ trễ từ timestamp ảnh đầu vào tới lúc tracker chuẩn bị publish ảnh debug.
- `Detector processing`: thời gian xử lý detector trong callback.
- `Transport/queue`: phần còn lại, gồm thời gian ảnh đi qua camera bridge/ROS queue trước khi detector xử lý.

Nếu muốn xem chính xác ảnh debug có marker hay không, topic `/siyi/fractal_debug` cũng hiển thị `Marker Dist` và `IDs`.

### Cách chạy đo liên tục

Nếu bạn muốn di chuyển marker liên tục từ khoảng 70 cm tới 540 cm, chạy logger mà không cần nhập khoảng cách kỳ vọng:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.162 \
  enable_csv_logger:=true \
  logger_config_id:=continuous \
  logger_resolution:=1280x720 \
  logger_tag_size_cm:=16.2 \
  logger_trial_label:=continuous_70_to_540cm \
  logger_notes:=sweep_70_to_540cm
```

Sau đó bạn có thể vừa cầm marker vừa đi xa dần, hoặc đặt marker lần lượt ở nhiều khoảng cách. Logger sẽ ghi liên tục toàn bộ các mẫu tracker thấy được. Khi xong, nhấn `Ctrl+C`; file CSV sẽ nằm trong `tracking_logs`.

Quy trình gợi ý:

1. Bắt đầu ở khoảng 70 cm.
2. Giữ marker đủ rõ trong khung hình.
3. Di chuyển dần ra xa tới 140 cm, 210 cm, 280 cm, rồi tiếp tục tới 540 cm.
4. Nếu muốn dữ liệu sạch hơn, dừng 3 đến 5 giây tại mỗi khoảng cách để có nhiều mẫu ổn định.
5. Dừng launch bằng `Ctrl+C`.

Sau khi đo, xem file log:

```bash
ls -lh ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs
```

Xem nhanh vài dòng:

```bash
head ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs/fractal_tracking_*.csv
```

Lọc các dòng tracker đang bám marker:

```bash
awk -F, 'NR==1 || $18=="TRACKING"' \
  ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs/fractal_tracking_*.csv
```

Lọc các mẫu có khoảng cách đo được trong khoảng 70 cm đến 140 cm:

```bash
awk -F, 'NR==1 || ($18=="TRACKING" && $24>=70 && $24<=140)' \
  ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/tracking_logs/fractal_tracking_*.csv
```

Trong CSV hiện tại, cột `$18` là `state_name` và cột `$24` là `distance_cm`.

### Cấu hình test kiểu bảng report

Bạn có thể ghi đúng các dòng cấu hình như bảng test:

```text
Config | Resolution | Tag size | Distance
A1     | 640x480    | 20 cm    | 5 m
A2     | 640x480    | 20 cm    | 8 m
A3     | 640x480    | 20 cm    | 10 m
B1     | 1280x720   | 20 cm    | 5 m
B2     | 1280x720   | 20 cm    | 8 m
C1     | 640x480    | 10 cm    | 1 m
C2     | 640x480    | 10 cm    | 2 m
E1     | 640x480    | 4 cm     | 0.3 m
```

Ví dụ chạy config `B1`, marker 20 cm, khoảng cách danh nghĩa 5 m:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.20 \
  enable_csv_logger:=true \
  logger_config_id:=B1 \
  logger_resolution:=1280x720 \
  logger_tag_size_cm:=20 \
  logger_test_distance_m:=5 \
  logger_expected_distance_cm:=500 \
  logger_trial_label:=B1_1280x720_20cm_5m
```

Ví dụ chạy config `E1`, marker 4 cm, khoảng cách 0.3 m:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.04 \
  enable_csv_logger:=true \
  logger_config_id:=E1 \
  logger_resolution:=640x480 \
  logger_tag_size_cm:=4 \
  logger_test_distance_m:=0.3 \
  logger_expected_distance_cm:=30 \
  logger_trial_label:=E1_640x480_4cm_0p3m
```

Nếu đo liên tục và không có mốc thật cố định, bỏ `logger_expected_distance_cm` và đặt `logger_test_distance_m:=0.0`.

Nếu máy không có `nvidia-smi` nhưng bạn vẫn muốn điền %GPU cố định vào CSV, thêm:

```bash
logger_gpu_percent_override:=0
```

hoặc thay `0` bằng số bạn đo được từ công cụ khác.

### Cách chạy một mốc đo tùy chọn

Nếu bạn muốn đo từng mốc cố định để tính sai số ngay trong CSV, truyền thêm `logger_expected_distance_cm`.

Ví dụ đo ở khoảng cách thật 70 cm:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.162 \
  enable_csv_logger:=true \
  logger_expected_distance_cm:=70 \
  logger_test_distance_m:=0.7 \
  logger_trial_label:=70cm
```

Ví dụ đo ở 540 cm:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.162 \
  enable_csv_logger:=true \
  logger_expected_distance_cm:=540 \
  logger_test_distance_m:=5.4 \
  logger_trial_label:=540cm
```

Nếu muốn chỉ chạy logger riêng, trong khi tracker đã chạy ở terminal khác:

```bash
ros2 run precision_landing fractal_tracking_csv_logger --ros-args \
  -p config_id:=continuous \
  -p resolution:=1280x720 \
  -p tag_size_cm:=16.2 \
  -p trial_label:=continuous_70_to_540cm
```

Nếu muốn logger riêng có khoảng cách kỳ vọng:

```bash
ros2 run precision_landing fractal_tracking_csv_logger --ros-args \
  -p expected_distance_cm:=70 \
  -p trial_label:=70cm
```

## 7. Chạy Với MAVROS Khi Cần Nối UAV Thật

Chỉ dùng bước này sau khi test camera + tracker ổn định.

Nếu Pixhawk kết nối USB:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=true \
  fcu_url:=/dev/ttyACM0:57600
```

Nếu MAVROS dùng UDP:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=true \
  fcu_url:=udp://:14540@127.0.0.1:14580
```

Kiểm tra MAVROS:

```bash
ros2 topic echo /mavros/state --once
```

Kỳ vọng:

```text
connected: true
```

## 8. Lỗi Hay Gặp

### Không mở được RTSP stream

Kiểm tra:

```bash
ping 192.168.168.16
```

Nếu ping không được, máy tính chưa vào đúng mạng của camera hoặc IP camera khác.

Nếu ping được nhưng RTSP fail, thử xem stream bằng VLC hoặc ffplay:

```bash
ffplay rtsp://192.168.168.16:8554/main.264
```

### Ảnh bị ngược đầu

Với launch khuyên dùng `precision_landing real_fractal_detect.launch.py`, sửa file:

```text
~/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/precision_landing/config/rtsp_publisher_params.yaml
```

Đổi:

```yaml
flip_180: true
```

Sau đó build/source lại và restart launch:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select precision_landing
source install/setup.bash
```

Với cấu hình hiện tại của test thật, mặc định đang là:

```yaml
flip_180: false
```

### Có ảnh nhưng không detect marker

Kiểm tra:

- Marker có đúng `marker.png` của repo không.
- Marker có đủ sáng và nằm gọn trong khung hình không.
- Kích thước `marker_size` có đúng với marker thật không.
- Camera calibration có được publish qua `/siyi/camera_info` không.
- Nếu marker quá gần/quá xa, đưa marker vào khoảng nhìn rõ hơn.

### Pose sai tỷ lệ

Thường do `marker_size` sai. Ví dụ marker ngoài cùng 16.2 cm thì phải chạy:

```bash
ros2 launch precision_landing real_fractal_detect.launch.py \
  enable_mavros:=false \
  marker_size:=0.162
```

### Sửa config nhưng launch vẫn dùng giá trị cũ

Build/source lại:

```bash
cd ~/PX4/examples/SITL_PrecisionLanding/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select precision_landing siyi_camera_bridge
source install/setup.bash
```

Sau đó restart launch.
