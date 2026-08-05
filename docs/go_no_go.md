# Go/No-Go — kiểm trước mỗi lượt bay

`scripts/go_no_go.sh` tự động hoá được 3 việc: môi trường build
(`verify_build_env.sh`), tiến trình cũ còn sót, và 3 lệnh kiểm trước bay
(`use_sim_time`, controller active, MAVROS connected — README.md §2.2). Nó
**không có mắt** — mấy việc cần nhìn thì vẫn phải tự kiểm bằng checklist dưới
đây.

```bash
./scripts/go_no_go.sh
```
`GO` (exit 0) hoặc `NO-GO`/`FAIL` (exit 1) kèm đúng dòng cần sửa. An toàn để
chạy nhiều lần — chỉ đọc (`echo`/`param get`/`list`), không publish, không
gọi service, giống triết lý "quan sát viên thụ động" của
`m3_full_loop_monitor.py`.

## Checklist mắt người (script không tự làm được)

| # | Kiểm | Đạt khi |
|---|---|---|
| 1 | `pxh>` (T1) | đã tới prompt, không còn dòng khởi động chạy |
| 2 | Marker trong lòng box | nhìn Gazebo hoặc `rqt_image_view /gimbal_camera`: ô fractal đen-trắng hiện rõ trên sàn, không bị nắp che (mở nắp trước — README §2.1) |
| 3 | HUD (T7, `/landing/annotated_image`) | cửa sổ đang mở, "Marker Dist/IDs" và "BOX: \<STATE\>" cập nhật, xanh lá khi `WAITING_FOR_LANDING(7)` |
| 4 | Box đang `EMPTY` | vừa bật lượt mới, chưa từng bay — nếu lượt trước đã CHARGING/IDLE, restart T5 để reset (không tự về EMPTY) |
| 5 | Arm được | `pxh> commander check` in `Preflight check: OK`; đã `param set NAV_DLL_ACT 0` **hoặc** đã mở QGroundControl |
| 6 (split-domain) | Cầu (T7 của run-sheet M4) đang chạy | `ddsrouter`/`dib_split_bridge` in dòng khởi động; `dib_split_bridge` từ M5 còn in heartbeat mỗi 10s — không thấy heartbeat mới trong >10s là cầu chết |

## Triệu chứng → nguyên nhân thật (rút từ Phụ lục A của README.md)

| Triệu chứng | KHÔNG phải | Nguyên nhân thật | Đọc thêm |
|---|---|---|---|
| Box "spawn hỏng" — `gz model --list` không thấy | spawn lỗi | Có thật, chỉ là **vô hình**: thiếu `GZ_SIM_RESOURCE_PATH` ở T1 (đặt ở launch spawn không có tác dụng — gz server do PX4 khởi động mới là bên phân giải `model://`) | A.5 |
| Controller còn `unconfigured` | build lỗi | `controller_manager` timeout 10s (Humble) lúc mới khởi tạo — hoàn tất tay 2 bước `configure` → `active` | A.5 |
| Tracker vẽ đỏ `sync N/A: clock mismatch` | lỗi tracker | T4 dùng nhầm `mavros px4.launch` (không có `use_sim_time`) thay vì `sitl_mavros.launch.py` | A.6 |
| `/landing/pose_sync_ms` "does not appear to be published yet" TRƯỚC khi bay | lỗi | Bình thường — topic chỉ có sau khi drone bay. Đang bay mà ra `-1.0` mới là lệch đồng hồ | A.6 |
| `Preflight Fail: No connection to the GCS`, FSM đứng `IDLE`, không log gì về box/tracker | lỗi ROS/box | Thiếu `NAV_DLL_ACT=0` hoặc chưa mở QGroundControl — đừng đi lùng lỗi phía box | A.6 |
| Drone bay mất hàng nghìn km | lỗi GPS/EKF | Thiếu fixture GPS box (T6) → `box_info.latitude/longitude=0` | A.7 |
| FSM bỏ qua toàn bộ bắt tay, không báo lỗi gì | bug FSM | `box_id` lệch giữa `box_state_manager.yaml` và `offboard_precland_params.yaml` — xác nhận bằng log `Derived box_telemetry_topic=...` | A.7 |
| Flare sớm hoặc cắm xuống đất | lỗi điều khiển | `marker_size` không khớp plane thật (đen = 80.12% cạnh ảnh) | A.7 |
| Máy lag ngay từ đầu lượt chạy mới | máy yếu | Tiến trình lượt trước còn sót — `./scripts/stop_pipeline.sh` (KHÔNG gõ tay `pkill -f`, tự giết chính shell đang gõ) | A.3 |
| Máy <8GB ì ạch / tốn RAM | rò rỉ bộ nhớ | Mesh `BOX PAD1.0_simple.dae` (3.58 triệu tam giác, chỉ để nhìn) — giảm mesh hoặc `HEADLESS=1` | A.9 |
| (split-domain) box kẹt `SECURING_DRONE`, không tới `CHARGING` | cầu hỏng | Thiếu `/dock/drone_power` trong allowlist cầu — fixture SITL bắt buộc, không phải hợp đồng thật | A.10, `docs/m4.md` Phụ lục E.2 |
| (split-domain) box kẹt `EMPTY`, `WAIT_BOX_READY` timeout 30s → `FALLBACK` | lỗi FSM | Cầu chết hoặc thiếu `whitelist-interfaces` per-participant | A.10, `docs/m4.md` Phụ lục B.1, I.2 |
