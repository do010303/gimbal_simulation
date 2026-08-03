# precision_landing

Tracker fractal + FSM hạ cánh (C++) + cầu telemetry MAVROS→dib_msgs.

**Cách chạy nằm ở README gốc của repo.** File này là tài liệu **đọc log và chẩn
đoán** — mở khi một lượt chạy có gì đó không như ý.

## 1. Node và topic

| Node | Vai trò |
|---|---|
| `aruco_fractal_tracker` | Dò marker fractal, publish pose + HUD `/landing/annotated_image` |
| `offboard_precland_controller` | FSM hạ cánh, bắt tay box qua `BoxLink` |
| `mavros_to_dib_telemetry` | MAVROS → `d<drone_id>/telemetry` |
| `rtsp_publisher` | Camera IP/RTSP → ROS (dùng cho camera thật) |

Topic hay dùng nhất:

| Topic | Ý nghĩa |
|---|---|
| `/landing/annotated_image` | HUD — **topic để mở rqt_image_view** |
| `/landing/target_camera` | `dib_msgs/LandingTarget6D` tracker phát ra |
| `/landing/pose_sync_ms` | Lệch dấu thời gian ảnh ↔ pose; `-1` = lệch đồng hồ |
| `/aruco_fractal_tracker/poses` | Pose marker trong khung camera |
| `/b<box_id>/telemetry` | Trạng thái box, cũng là nguồn cho dòng `BOX:` trên HUD |

Kiểm nhanh khi nghi topic chết:
```bash
ros2 topic hz /gimbal_camera                    # camera bridge còn sống
ros2 topic hz /landing/target_camera            # tracker còn phát target
ros2 topic hz /mavros/setpoint_position/local   # setpoint: cần >=20 Hz khi OFFBOARD
ros2 topic echo --once /mavros/state            # connected: true
```
> `ros2 topic list`/`echo` trả về rỗng trong khi node vẫn chạy thường là **daemon
> cũ**. `ros2 daemon stop`, hoặc thêm `--no-daemon` để hỏi thẳng.

## 2. Đọc HUD

Panel góc dưới trái của `/landing/annotated_image`, 7 dòng. Hai dòng đáng nhìn
nhất khi chạy drone-in-a-box:

- **`Marker Dist / IDs`** — drone có thấy marker không.
- **`BOX: <STATE>(<n>)`** — box đã mở nắp chưa. Xanh lá ở `WAITING_FOR_LANDING(7)`
  nghĩa là box đã sẵn sàng đón drone này.
  - `BOX: no telemetry` — không có ai publish `/b<box_id>/telemetry`. Đúng và
    bình thường với các pipeline legacy không có box; nếu đang chạy M3 thì
    thường là **`box_id` lệch** (xem mục 4).
  - `[STALE 12s]` — có nhận rồi nhưng đã ngừng: phía box chết hoặc mạng đứt.

### Marker fractal tự rụng tầng

`ids=[0,1,2]` trên cao → `ids=[1,2]` ở khoảng 0.65 m khi tầng ngoài 0.50 m ra
khỏi khung hình. Đây là thiết kế, không phải mất bám.

### `UAV ENU U` khác `MARKER DIST` là ĐÚNG

Hai số đo từ hai gốc khác nhau: `U` tính từ điểm **cất cánh**, `MARKER DIST` từ
**camera** tới marker trên nóc box.
```
U − MARKER DIST ≈ cao độ marker − cao độ camera so base_link ≈ 0.637 − 0.118 = 0.52 m
```
(0.118 đọc từ model: gimbal `z=+0.28`, sensor `z=−0.162`.) Log bay giữ hiệu này
**hằng số 0.48–0.54 m**. Hằng số chứ không tỷ lệ — đó chính là bằng chứng loại
trừ khả năng sai `marker_size`.

## 3. Latency và lệch đồng hồ (quan trọng khi chạy HITL)

`E2E latency = now() − image_stamp` **chỉ là độ trễ khi hai đầu chung đồng hồ**.
Camera đóng dấu bằng đồng hồ riêng, hoặc NTP lệch, thì cùng phép trừ ấy cho ra
**độ lệch đồng hồ** trông y hệt độ trễ khổng lồ. Đây là lý do HITL hay báo e2e
rất lớn trong khi `Detector processing` (đo bằng `steady_clock`, miễn nhiễm) chỉ
vài ms.

Phân biệt bằng **hình dạng**, không bằng độ lớn:

| | sàn (floor) | dao động (jitter) |
|---|---|---|
| Độ trễ thật | nhỏ | thấy rõ, đổi từng khung |
| Lệch đồng hồ | lớn | gần bằng 0 |

Tracker theo dõi sàn trượt 10 giây và tự gắn cờ
`[CLOCK OFFSET? floor=2478 jitter=2]`. Thấy cờ này thì **đừng đi tối ưu hiệu
năng** — đồng bộ thời gian trước.

Trong SITL, nguyên nhân gần như luôn là MAVROS chạy đồng hồ tường: phải dùng
`sitl_mavros.launch.py`, vì `mavros px4.launch` **không khai báo** arg
`use_sim_time` nên truyền vào bị bỏ qua trong im lặng.

```bash
ros2 topic echo --once --field data /landing/pose_sync_ms  # số dương; -1.0 là lệch đồng hồ
ros2 param get /mavros/mavros_node use_sim_time            # True
```
> Node là `/mavros/mavros_node`. `/mavros` tự nó **không tồn tại** — trả
> `Node not found` là sai tên node, không phải MAVROS hỏng.

## 4. Ba cấu hình hay sai — xác nhận bằng log

Ba thứ phải khớp mới chạy được (`box_id`, GPS của box, `marker_size` ↔ plane)
liệt kê ở **mục 2.5 README gốc**. Từ phía log, đây là cách xác nhận từng cái:

| Nghi ngờ | Log xác nhận |
|---|---|
| `box_id` lệch | Cả tracker lẫn controller phải in `Derived box_telemetry_topic='/b2/telemetry' from box_id=2`. Không thấy, hoặc thấy `/b1/`, là lệch — HUD sẽ hiện `BOX: no telemetry` và FSM **bỏ qua toàn bộ bắt tay mà không báo lỗi**. |
| Box không có GPS | `box_info.lat/lon = 0` → `st_goto_box()` tính setpoint cách hàng nghìn km, drone bay mất. Trong SITL phải chạy fixture publish `/gps`. |
| `marker_size` lệch plane | Pose sai **thang đo** → sai độ cao → flare sớm hoặc cắm xuống. Dấu hiệu phân biệt: hiệu `U − MARKER DIST` **đổi theo độ cao** thay vì giữ hằng số 0.48–0.54 m (mục 2). |

## 5. Chuỗi log của một lượt chạy đạt

FSM drone và box đan xen theo đúng quan hệ nhân quả:
```
DRONE  -> GOTO_BOX -> PRELANDING_CHECK -> WAIT_BOX_READY
BOX    -> PREPARING_FOR_LANDING(6) -> WAITING_FOR_LANDING(7)
DRONE  -> START -> HORIZONTAL_APPROACH -> DESCEND_ABOVE_TARGET -> FINAL_APPROACH
MAVROS -> landed_state=ON_GROUND
BOX    -> SECURING_DRONE(8) -> CHARGING(9)
```
- Box chỉ rời `EMPTY` **sau** khi drone vào `WAIT_BOX_READY` — chính
  `REQUEST_LANDING` của drone gây ra, không phải trùng hợp thời gian.
- Drone chỉ vào `START` **sau** khi box báo `WAITING_FOR_LANDING` — không hạ
  xuống trước khi nắp mở.
- **Không** `SEARCH` kéo dài, **không** `FALLBACK`.

Vòng đời khép tới `CHARGING` — sau khi drone chạm đất **còn ~35–40 giây nữa**,
đừng Ctrl+C sớm:
```
offboard_precland: LANDING COMPLETE — disarmed. Waiting for box to secure and charge.
box_state_manager: Box in SECURING_DRONE state, securing state: 5   (kẹp + đóng nắp)
offboard_precland: BoxLink: sending TURN_OFF_DRONE to b2 (agent_id=12)
box_hardware_adapter: /dock/power_button/cmd command=0 -> drone power OFF
mavros_to_dib_telemetry: Dock power OFF: stopping publishing d1/telemetry
box_state_manager: Box in CHARGING state
offboard_precland: Box reached CHARGING — drone-in-a-box cycle complete
```

## 6. Những dòng log TRÔNG như lỗi nhưng không phải

| Log | Thực chất |
|---|---|
| `Ground contact: blocked by 20.5cm → force-disarm` | Drone dừng cao hơn mặt đất 0.6 m vì **đang đứng trên box**; nhánh force-disarm xử lý đúng tình huống này |
| `TURN_OFF_DRONE` lặp mỗi 3 giây | Đúng thiết kế: idempotent, box giữ như cờ dính và chỉ tiêu thụ khi kẹp/nắp đã đóng xong |
| `command 520 unsupported` | Capability request MAVLink cũ, không liên quan lệnh hạ cánh |
| `FSM đứng ở IDLE` khi chưa bay | Đúng — controller chỉ rời `IDLE` khi MAVROS báo drone đang bay |
| `VER: command plugin service call failed!` | Cảnh báo khởi động của MAVROS, tự hết |

### Vì sao SITL phải giả lập cú cắt điện

`box_manager` rời `POWER_OFF → DONE` (rồi `CHARGING`) khi telemetry drone **im
quá 5 giây**. Phần cứng thật: box cắt nguồn nên máy đồng hành tắt, im lặng miễn
phí. SITL: MAVROS chạy mãi, nên adapter publish `/dock/drone_power` và
`mavros_to_dib_telemetry` ngừng phát khi nhận `false`. Thiếu mắt xích này thì
box kẹt ở `POWER_OFF` vĩnh viễn.

## 7. Đo độ ồn log

```bash
# chạy dib_bringup với: ... 2>&1 | tee /tmp/bringup.log
wc -l /tmp/bringup.log          # cả chuyến ~2 phút: DƯỚI 40 dòng, không dòng lặp theo tick
grep 'Box in' /tmp/bringup.log  # mỗi state đúng MỘT dòng
```

## 8. Đọc số sai số hạ cánh cho đúng

```
TOUCHDOWN: drone=(2.5104,-2.5863) aim=(2.5200,-2.5000) aim_error=0.090m alt_agl=0.664m
```
- `drone=` là **vị trí thật** → sai số hạ cánh THẬT = `drone=` trừ marker thật
  `(2.5129, −2.5896)`.
- `aim=` là điểm ngắm (ước lượng marker của tracker); `aim_error` đo **chất lượng
  bám của vòng điều khiển**, không phải độ chính xác hạ cánh.

Mỗi độ cao có tên riêng: `alt_agl` (so điểm cất cánh, dùng ở `[YAW-3D]` và
`FINAL_APPROACH`), `alt_pad` (so marker, dùng ở `APPROACH`/`DESCEND`).

> Mọi con số "sai số hạ cánh" ghi **trước 2026-07-23** lấy từ `final_xy` = điểm
> ngắm, nên thực ra là sai số **ước lượng marker**, đừng đem so với `TOUCHDOWN`.

## 9. Tài liệu thiết kế

`docs/fsm_diagram.md`, `docs/refactoring_architecture.md`,
`docs/altitude_bug_analysis.md` trong chính gói này. Mốc M3 đầy đủ:
`docs/m3.md` ở gốc repo.

## 10. `require_rtk` và `DroneTelemetry.error` (REQ_UAV_FLY_0020)

`offboard_precland_controller` nhận param `require_rtk` (mặc định `false`,
truyền qua launch arg `sitl_precland.launch.py require_rtk:=true`). Khi bật và
drone chưa có RTK fix lúc `PRELANDING_CHECK`, controller log `PRELANDING_CHECK:
require_rtk set but no RTK fix -- unsafe. FALLBACK.` và chuyển FSM sang
`FALLBACK` (hạ cánh dự phòng) thay vì bắt tay box.

`mavros_to_dib_telemetry` theo dõi `/lander/state`: bất kỳ lần vào
`FALLBACK` nào (không riêng no-RTK — mất marker, box không sẵn sàng, timeout…)
đều SET `DroneTelemetry.error = [dib_msgs::msg::DroneTelemetry::ERR_FALLBACK_LANDING]`
(mã `0002`). Cờ này **latch** — giữ nguyên tới khi FSM quay lại `IDLE`/
`FLIGHT_IN_PROGRESS` ở chuyến bay kế tiếp, vì `FALLBACK → DONE` chuyển trong
~30 ms nên một cờ không latch gần như không quan sát được qua `ros2 topic
echo`. `error` rỗng `[]` ở chuyến bay bình thường.
