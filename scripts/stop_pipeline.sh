#!/usr/bin/env bash
# Dừng toàn bộ pipeline drone-in-a-box.
#
# VÌ SAO CẦN SCRIPT NÀY thay vì gõ thẳng `pkill -f 'px4|gz sim|...'`:
# `pkill -f` so khớp với TOÀN BỘ dòng lệnh của mọi tiến trình — kể cả dòng lệnh
# của chính cái shell đang gõ, vì dòng đó có chứa chuỗi 'px4|gz sim|...'. Shell
# tự giết mình ngay ở lệnh pkill đầu tiên, lệnh thứ hai không bao giờ chạy, và
# người dùng tưởng đã dọn sạch trong khi Gazebo + PX4 vẫn đang ăn vài GB RAM.
#
# Ở đây chuỗi pattern nằm trong BIẾN, không nằm trên dòng lệnh, và ta còn loại
# trừ tường minh script này cùng toàn bộ tiến trình cha của nó.
set -u

PATTERNS='px4|gz sim|gz gui|gzserver|ruby.*gz|robot_state_publisher|spawner|controller_manager|mavros|offboard_precland|aruco_fractal|box_state_manager|box_hardware|mavros_to_dib|landing_target_bridge|rtsp_publisher|ros_gz|parameter_bridge|rqt_image_view|m3_full_loop_monitor|box_gps_publisher|sitl_fixtures'

# Chính script này + mọi tiến trình cha: tuyệt đối không đụng tới.
SAFE=" "
pid=$$
while [ "$pid" -gt 1 ]; do
    SAFE="$SAFE$pid "
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    [ -z "$pid" ] && break
done

targets() {
    # pgrep tự loại chính nó; ta loại thêm script + tổ tiên.
    for p in $(pgrep -f "$PATTERNS" 2>/dev/null); do
        case "$SAFE" in *" $p "*) continue ;; esac
        echo "$p"
    done
}

n=$(targets | wc -l)
if [ "$n" -eq 0 ]; then
    echo "Không có tiến trình pipeline nào đang chạy."
else
    echo "Đang dừng $n tiến trình..."
    # TERM trước để Gazebo/PX4 kịp đóng file log tử tế.
    for p in $(targets); do kill -TERM "$p" 2>/dev/null; done
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        [ "$(targets | wc -l)" -eq 0 ] && break
        sleep 0.5
    done
    # Còn sót thì KILL. gz sim hay lì ở bước này.
    left=$(targets | wc -l)
    if [ "$left" -ne 0 ]; then
        echo "Còn $left tiến trình lì, gửi SIGKILL..."
        for p in $(targets); do kill -9 "$p" 2>/dev/null; done
        sleep 1
    fi
fi

# Daemon ros2 cache discovery giữa các phiên; không dừng thì lần chạy sau
# `ros2 topic list` trả về rỗng dù node vẫn sống.
ros2 daemon stop >/dev/null 2>&1 || true

remain=$(targets | wc -l)
if [ "$remain" -eq 0 ]; then
    echo "sach"
else
    echo "VẪN CÒN $remain tiến trình:"
    for p in $(targets); do ps -o pid=,cmd= -p "$p" 2>/dev/null | cut -c1-100; done
    exit 1
fi
