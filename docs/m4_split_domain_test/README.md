# M4 split-domain — run sheet (one host, two domains, DDS-Router)

Box side runs `ROS_DOMAIN_ID=42`, drone side `ROS_DOMAIN_ID=0`, everything
`ROS_LOCALHOST_ONLY=1`. The bridge carries ONLY the 3 contract interfaces.

Default bridge is **DDS-Router 2.2.0**; `dib_domain_bridge` (apt
`domain_bridge`) is kept as a fallback — see `ros2_ws/src/dib_domain_bridge/README.md`.

> **Vì sao 2.2.0 chứ không phải bản mới nhất.** Humble link Fast DDS 2.6.11.
> Mọi bản DDS-Router **3.x** kéo theo Fast DDS **3.x** (v3.5.1→3.6.1), và một
> participant Fast DDS 3.6 **không discovery được** endpoint 2.6 → router chạy,
> báo "running", nhưng bắc cầu **con số không**. Đo hai lần (2026-07-30 và
> 2026-08-03 với bản 3.5.1 mới build): talker phát liên tục, listener không
> nhận gì. Không sửa được bằng cấu hình — router link Fast DDS nào là do lúc
> build. 2.2.0 pin Fast DDS 2.14.0, vẫn dòng 2.x, nói chuyện được với 2.6.

> **Vì sao `/b2/cmd` không còn trong danh sách bắc cầu.** DDS-Router 2.2.0
> không bao giờ route **reply** của một ROS 2 service qua domain (request qua,
> reply mất — đo kỹ với cả `dib_msgs/BoxCmd` lẫn service chuẩn
> `demo_nodes_cpp AddTwoInts`). Thay vì ghép thêm domain_bridge chỉ vì một
> service, lệnh drone→box đã chuyển sang **topic** `b2/drone_cmd`. An toàn:
> reply cũ vốn vô nghĩa — `box_state_manager` set `success=true` ngay dòng đầu
> trước khi xử lý gì, telemetry mới là xác nhận thật. Service `b2/cmd` vẫn còn
> nguyên cho vai trò operator/server, chỉ là không đi qua ranh giới domain.

## Prereqs (once)

```bash
# Build DDS-Router 2.2.0 từ nguồn (~4 phút, KHÔNG có gói apt)
mkdir -p ~/DDS-Router-2.2/src && cd ~/DDS-Router-2.2
cp ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/precision_landing/config/dds_router_2.2.0.repos ddsrouter.repos
vcs import src < ddsrouter.repos
source /opt/ros/humble/setup.bash && colcon build
```
`rosdep install` bị bỏ qua có chủ đích: nó abort vì `package.xml` của `fastcdr`
có thuộc tính `<license file=...>` mà schema rosdep từ chối — lỗi *định dạng
manifest*, không phải thiếu dependency.

Cầu dự phòng (tuỳ chọn): `sudo apt install -y ros-humble-domain-bridge` rồi
`cd ros2_ws && colcon build --packages-select dib_domain_bridge`.

## Header per terminal

Common (every terminal):
```bash
source /opt/ros/humble/setup.bash
source ~/gz_ros2_control_ws/install/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
```
Then add the domain line — **box terminals** `export ROS_DOMAIN_ID=42`,
**drone terminals** `export ROS_DOMAIN_ID=0`. The bridge terminal (T7) needs
NEITHER domain export — it takes both domains from its config/arguments.

## Terminals

| T | Domain | Lệnh |
|---|---|---|
| 1 | 42 | `export GZ_SIM_RESOURCE_PATH=$HOME/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/box_simulation/share`<br>`cd ~/PX4 && PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_x500_gimbal_fractal_aruco_landing` |
| 2 | 42 | `ros2 launch box_simulation box_spawn_only.launch.py` |
| 5 | 42 | `ros2 launch precision_landing dib_bringup.launch.py include_telemetry_bridge:=false` |
| 6 | 42 | `ros2 launch ~/PX4/examples/SITL_PrecisionLanding/docs/m3_box_handshake_test/sitl_fixtures.launch.py` |
| 3 | 0  | `ros2 launch precision_landing sitl_precland.launch.py` |
| 4 | 0  | `ros2 launch precision_landing sitl_mavros.launch.py` |
| 5b| 0  | `ros2 run precision_landing mavros_to_dib_telemetry --ros-args -p drone_id:=1` |
| 7 | — | **cầu** — xem hai lựa chọn ngay dưới |
| 8 | 0  | **driver tự động** — `python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m4_split_domain_test/m4_full_loop_monitor.py` (chỉ cần cho M4.4, xem mục đó) |

**T7 mặc định (DDS-Router):**
```bash
cd ~/DDS-Router-2.2 && source install/setup.bash
./install/ddsrouter_tool/bin/ddsrouter -c \
  ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/src/precision_landing/config/dds_router_split.yaml
```
**T7 dự phòng (domain_bridge):**
```bash
ros2 run dib_domain_bridge dib_split_bridge 42 0
```

> **T5 phải có `include_telemetry_bridge:=false`.** `mavros_to_dib_telemetry`
> đọc MAVROS nên nó thuộc **phía drone**; `ROS_DOMAIN_ID` là per-process nên
> launch phía box không được khởi động nó. T5b chạy nó riêng bên domain drone.

> Camera + `/clock` KHÔNG cần bắc cầu: T3 (`sitl_precland`) tự có image/clock/
> camera_info bridge đọc gz-transport (không scope theo ROS_DOMAIN_ID).

## What the bridge carries

**3 giao diện hợp đồng** (có cả trên phần cứng thật):

| Interface | Kiểu | Hướng |
|---|---|---|
| `/b2/telemetry` | topic `dib_msgs/msg/BoxTelemetry` | box 42 → drone 0 |
| `/d1/telemetry` | topic `dib_msgs/msg/DroneTelemetry` (BEST_EFFORT/VOLATILE) | drone 0 → box 42 |
| `/b2/drone_cmd` | topic `dib_msgs/msg/BoxCmd` (REQUEST_LANDING / TURN_OFF_DRONE) | drone 0 → box 42 |

**+ 1 fixture CHỈ CHO SITL** (bỏ trên phần cứng thật):

| Interface | Kiểu | Hướng |
|---|---|---|
| `/dock/drone_power` | topic `std_msgs/msg/Bool` (RELIABLE/**TRANSIENT_LOCAL**) | box 42 → drone 0 |

> **Thiếu `/dock/drone_power` là box KẸT Ở `SECURING_DRONE`, không bao giờ tới
> `CHARGING`.** Box rời `POWER_OFF → DONE → CHARGING` chỉ khi `d1/telemetry`
> **im quá 5 giây** (`securing_state_manager.cpp`). Phần cứng thật: box cắt
> điện → máy tính drone tắt → im lặng miễn phí. SITL: MAVROS vẫn chạy, nên
> `box_hardware_adapter` publish cờ `/dock/drone_power`, và
> `mavros_to_dib_telemetry` **ngừng phát** khi nhận `false`. Ở single-domain
> (M1–M3) cờ này đi thẳng; ở split-domain nó **phải qua cầu**, nếu không node
> phía drone không bao giờ biết đã bị cắt điện.
>
> Triệu chứng đúng của lỗi này (đã gặp 2026-08-05): box log
> `/dock/power_button/cmd command=0 -> drone power OFF` rồi đứng im ở
> `SECURING_DRONE(8)`; drone log `DONE: waiting for box to charge (…s/90s,
> box_state=8)` đếm tới hết giờ; và **không** có dòng `Dock power OFF:
> stopping publishing d1/telemetry` bên drone.

## M4.1 — chứng minh cô lập (CHƯA chạy bridge)

Chạy T1–T6 + T3/T4/T5b, **không** chạy T7. Kỳ vọng loop ĐỨNG:
```bash
# domain 42 (box):   phải ra 0
ros2 topic list | grep -c mavros
# domain 0 (drone):  phải ra 0
ros2 topic list | grep -c '/lid/status'
```
Bay → drone kẹt `WAIT_BOX_READY`, box `EMPTY` (REQUEST_LANDING không qua). ✅
(Đã PASS 2026-07-30: log drone in "AUTO.LAND detected without box telemetry",
đáp GPS lệch ~2.5m thay vì handshake.)

## M4.2 — bật bridge: 2 topic telemetry

Chạy T7. Kiểm bằng rclpy subscriber (**không** dùng `ros2 topic echo` — daemon
XML-RPC của nó hay treo/`!rclpy.ok()` với topic cross-domain dù cầu vẫn tốt;
xem `tier1/README.md` có sẵn đoạn script kiểm `/d1/telemetry`).

## M4.3 — lệnh drone→box qua topic `b2/drone_cmd`

Đây là chỗ DDS-Router từng chết khi còn là service. Giờ là topic:
```bash
# domain 0 (drone): gửi thử một lệnh như BoxLink gửi
ros2 topic pub --once /b2/drone_cmd dib_msgs/msg/BoxCmd \
  '{command: 23, reserve: 0, agent_id: 12}'
# domain 42 (box): box_state_manager phải log "Drone command received: 23"
```
`agent_id = drone_id*10 + 2` (2 = vai trò drone). Sai quy ước này thì
`drone_cmd_callback` bỏ qua trong im lặng.

**Tier-1 PASS 2026-08-05** (không Gazebo, `tier1/`): cả 3 giao diện qua cầu,
7/7 lệnh `REQUEST_LANDING` tới box; tắt router → drone vẫn publish nhưng box
dừng nhận (nhân quả sạch). Chi tiết: `tier1/README.md`.

`/dock/drone_power` cũng đã kiểm riêng (cả `true` lẫn `false` qua cầu, giữ
đúng TRANSIENT_LOCAL) trên **cả hai** cầu — DDS-Router và `dib_split_bridge`.

## Chứng minh cầu THẬT SỰ mang dữ liệu (không phải domain rò rỉ)

**DDS-Router không log từng message.** Kể cả chạy với `-d` hay
`--log-verbosity info --log-filter ".*"`, bản 2.2.0 chỉ in `DDS Router running.`
rồi im — đã kiểm. Đừng đi tìm dòng log "đã route topic X"; nó không tồn tại.
Bằng chứng phải lấy từ ba chỗ khác, và cả ba đều mạnh hơn một dòng log.

### 1. Socket mạng — cứng nhất, kiểm trong 10 giây

ROS 2 ánh xạ `ROS_DOMAIN_ID` sang cổng UDP theo công thức cố định
**`7400 + 250 × domain`**. Domain 0 → **7400**, domain 42 → **17900**. Hai
domain nghe hai cổng khác nhau nên **về mặt vật lý không nghe được nhau**.

```bash
# Lấy PID: chú ý pgrep bắt cả tiến trình `timeout` bọc ngoài, lấy PID python/ddsrouter thật
ps -eo pid,cmd | grep -F ddsrouter | grep -v grep
ss -uapn | grep -F "pid=<PID>" | awk '{print $4}' | sort -t: -k2 -n
```

Kết quả đo thật (2026-08-05):

| Tiến trình | Domain | Cổng UDP đang giữ |
|---|---|---|
| `box_side.py` | 42 | `17900`, `239.255.0.1:17900`, 17912, 17913 — **không có 7400** |
| `drone_side.py` | 0 | `7400`, `239.255.0.1:7400`, 7410, 7411 — **không có 17900** |
| `ddsrouter` | — | **`7400` VÀ `17900`** (cả unicast lẫn multicast, cả hai domain) |

Router là **tiến trình duy nhất** đứng chân ở cả hai domain. Hai node ROS không
có đường nào nghe thấy nhau. Vậy mọi message đã qua được đều đi qua router —
không còn khả năng nào khác.

### 2. Nhân quả — tắt cầu thì đứng

Xem M4.1 (chưa bật cầu → loop kẹt) và test tắt cầu giữa chừng ở M4.4. Ở tầng-1
đã đo: tắt router → drone vẫn publish `#6`,`#7` nhưng box **dừng nhận** sau `#5`.

### 3. Chính nội dung log ứng dụng

Mỗi dòng dưới đây là một message đã **vượt ranh giới domain**, vì bên phát và
bên nhận nằm ở hai domain khác nhau:

| Dòng log | Ở đâu | Bên phát |
|---|---|---|
| `Drone command received: 23` | box, domain 42 | `BoxLink`, domain 0 |
| `Drone telemetry connected=1` | box, domain 42 | `mavros_to_dib_telemetry`, domain 0 |
| `BoxLink: box_state 7 -> 8` | drone, domain 0 | `box_state_manager`, domain 42 |
| `Dock power OFF: stopping publishing d1/telemetry` | drone, domain 0 | `box_hardware_adapter`, domain 42 |

## M4.4 — nghiệm thu: vòng kín qua cầu

Hai kịch bản, chạy **liên tiếp trên cùng một pipeline đang sống** — không
tắt gì giữa hai kịch bản, kịch bản 3 dùng lại đúng lượt bay đang chạy dở của
kịch bản 2 (xem lý do ở cuối M4.3: `box_state_manager` không nhận
`REQUEST_LANDING` mới khi đã ở `CHARGING`, nên không có chuyện "bay lại từ
đầu" ở giữa).

> **Vì sao không dùng thẳng `m3_full_loop_monitor.py` ở đây.** Script đó
> subscribe `/box/state` trực tiếp — topic này chỉ tồn tại cục bộ domain box
> (42), KHÔNG nằm trong 3 giao diện được bắc cầu, nên một tiến trình chạy
> domain drone (0) không bao giờ thấy nó. `m4_full_loop_monitor.py` đọc
> trạng thái box từ field `box_state` lồng sẵn bên trong `b2/telemetry`
> (đã bắc cầu) thay vì subscribe `/box/state` — tiêu chí Pass giữ y hệt 8
> mục của M3.

### Kịch bản 2 — chạy đủ, có driver tự động chấm điểm (8/8 chính thức)

Chạy đủ T1→T7 như trên, cộng **T8**:
```bash
# T8 — domain 0, driver tự động, KHÔNG publish/gọi service gì
source /opt/ros/humble/setup.bash
source ~/PX4/examples/SITL_PrecisionLanding/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=1
python3 ~/PX4/examples/SITL_PrecisionLanding/docs/m4_split_domain_test/m4_full_loop_monitor.py
```
Bay `commander takeoff` / `commander land` ở T1 như thường lệ. Theo dõi T8 —
nó tự in trace `DRONE -> ...` / `BOX -> ...` theo thời gian thực, y hệt cách
đọc `m3_full_loop_monitor.py`. Bay trọn tới `CHARGING`, **để T8 chạy tiếp**
(chưa Ctrl+C) — sang thẳng kịch bản 3 dùng lượt bay kế tiếp.

> Muốn dừng ở đây (không làm kịch bản 3): Ctrl+C T8, kỳ vọng in ra
> **8/8 PASS**. Số liệu `aim_error`/`yaw_error` trong log T3 nên nằm quanh
> mức đã đo trước đó (≈2 cm, ≈0.01°).

### Kịch bản 3 — nhân quả: tắt cầu GIỮA CHỪNG một chuyến bay đang sống

Khác với M4.1 (chưa từng bật cầu): ở đây cầu đã chạy, đã mang telemetry thật
(T8 đã in `BOX GPS valid`, đã thấy box đổi trạng thái từ chuyến trước) —
rồi bị cắt ngay khi đang cần nó nhất. Nhân quả kiểu này chặt hơn nhiều so
với "chưa bao giờ bật".

**Bay lượt mới** (T1 `commander takeoff` rồi `commander land` lại — pipeline
T1–T7 vẫn đang sống từ kịch bản 2, không cần khởi động lại gì trừ box đã về
`EMPTY`). Đứng sẵn ở terminal T7, mắt theo dõi T8:

```
[   xx.xs] DRONE  -> GOTO_BOX              <- thấy dòng này thì SẴN SÀNG tay ở T7
[   xx.xs] DRONE  -> PRELANDING_CHECK      <- Ctrl+C T7 NGAY khi thấy dòng này
```
Cửa sổ giữa `PRELANDING_CHECK` và `WAIT_BOX_READY` chỉ tồn tại vài trăm ms
tới ~1 s (số đo các lần chạy trước), nên phải Ctrl+C **ngay khi** dòng
`PRELANDING_CHECK` vừa in ra — trước khi drone kịp gọi `request_landing()`.

> **Nếu cửa sổ quá ngắn để Ctrl+C kịp:** `offboard_precland_controller.cpp`
> (`st_prelanding_check()`) có một gate `test_hold_ok` **TEMP/TEST-ONLY**
> (tìm chuỗi `TEMP/TEST-ONLY`) ép `PRELANDING_CHECK` giữ tối thiểu 5 s trước
> khi cho qua `WAIT_BOX_READY`, đủ thời gian phản xạ. Bật bằng cách build
> lại `precision_landing` với gate đó còn nguyên; **PHẢI gỡ trước khi bay
> thật hoặc commit** — đây là code controller bay thật, gate 5s không có
> lý do tồn tại ngoài lúc test tay này.

**Kỳ vọng, 4 điều — tất cả đều PASS mới coi là đạt:**

| # | Quan sát ở đâu | Kỳ vọng |
|---|---|---|
| 1 | T8 | KHÔNG còn thấy `BOX -> PREPARING_FOR_LANDING` xuất hiện — box vẫn kẹt `EMPTY` |
| 2 | T3 (log drone, cục bộ, không qua cầu) | ~30 s sau khi vào `WAIT_BOX_READY`, in dòng timeout `box_ready_timeout` rồi `DRONE -> FALLBACK` (`box_ready_timeout_sec: 30.0`, `offboard_precland_controller.cpp:1487`) |
| 3 | T8 | `b2/telemetry` (box GPS/box_state) NGỪNG cập nhật ngay sau lúc Ctrl+C T7 — chứng minh cầu THẬT đã chết, không phải box tự đứng vì lý do khác |
| 4 | T2/T5 (log box) | `box_state_manager` không bao giờ nhận `REQUEST_LANDING`, ở nguyên `EMPTY` |

Nếu T8 vẫn thấy box đổi trạng thái **sau khi** đã Ctrl+C T7 → cầu chưa thật
sự chết. Kiểm lại đã tắt đúng tiến trình `ddsrouter` chưa (tránh nhầm với
bẫy "pkill tự sát" — dòng lệnh chứa chính pattern nó tìm, xem `m3.md` mục
"Đính chính 2026-07-31"); dùng Ctrl+C trực tiếp trên terminal T7 (không dùng
`pkill -f` mù), hoặc `kill -TERM <pid ddsrouter>` với PID lấy từ
`ps -eo pid,cmd | grep -F ddsrouter | grep -v grep`.

**Kết thúc:** Ctrl+C T8 để lấy log cuối, rồi `./scripts/stop_pipeline.sh` dọn
toàn bộ — không cần khôi phục cầu, kịch bản 3 là bài test cuối cùng của đợt
này.
