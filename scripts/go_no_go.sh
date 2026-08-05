#!/usr/bin/env bash
# Cổng kiểm GO/NO-GO — MỘT lệnh, chạy trước mỗi lượt bay (M5, hardening).
#
# Không thay verify_build_env.sh (đó là kiểm môi trường BUILD, chạy một lần)
# — script này gọi lại nó rồi kiểm thêm những gì chỉ biết được lúc PIPELINE
# ĐANG SỐNG: 3 lệnh kiểm trước bay vốn nằm rải trong README.md §2.2 ("Kiểm 3
# thứ trước khi bay") đưa vào đây để không ai quên gõ tay và không phải nhớ
# thuộc lòng.
#
# Chạy được ở 2 thời điểm khác nhau, tự nhận biết:
#   - TRƯỚC khi bật T1-T6: chỉ kiểm còn tiến trình cũ sót lại không (gợi ý
#     chạy scripts/stop_pipeline.sh) — đúng bài học M3.5 "máy lag gần như
#     luôn do tiến trình lần chạy trước còn sót".
#   - SAU khi T1-T6 đã lên (mavros đã publish /mavros/state): kiểm đủ 3 mục
#     trước bay thật.
#
# Không publish/gọi service gì — chỉ đọc (echo/param get/list), giống triết
# lý "quan sát viên thụ động" của m3_full_loop_monitor.py.
set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0;0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

FAIL=0
WARN=0

echo -e "${GREEN}=== GO/NO-GO — drone-in-a-box ===${NC}\n"

# --- 0. Môi trường build (tái dùng verify_build_env.sh, không viết lại) ---
echo "--- 0. Môi trường build ---"
if [ -z "${ROS_DISTRO:-}" ]; then
    echo -e "${RED}[FAIL] Chưa source ROS 2 ở terminal này.${NC} source /opt/ros/humble/setup.bash"
    FAIL=1
else
    ENV_LOG=$(mktemp)
    if bash "$REPO_DIR/verify_build_env.sh" >"$ENV_LOG" 2>&1; then
        echo -e "${GREEN}[OK] verify_build_env.sh sạch (không FAIL, có thể còn WARN — xem $ENV_LOG)${NC}"
    else
        echo -e "${RED}[FAIL] verify_build_env.sh báo lỗi — đọc $ENV_LOG trước khi bay${NC}"
        tail -5 "$ENV_LOG" | sed 's/^/       /'
        FAIL=1
    fi
fi

# --- 1. Tiến trình cũ còn sót từ lượt trước ---
# Cùng PATTERNS với scripts/stop_pipeline.sh (chỉ đọc, không kill ở đây).
# 'controller_manager/spawner', không phải 'spawner' trần — bare 'spawner'
# khớp nhầm gvfsd-trash/-network/-dnssd (chạy với cờ '--spawner ...' trên
# Ubuntu/GNOME), phát hiện được khi test script này lần đầu.
echo -e "\n--- 1. Tiến trình cũ còn sót ---"
PATTERNS='px4|gz sim|gz gui|gzserver|ruby.*gz|robot_state_publisher|controller_manager/spawner|controller_manager|mavros|offboard_precland|aruco_fractal|box_state_manager|box_hardware|mavros_to_dib|landing_target_bridge|rtsp_publisher|ros_gz|parameter_bridge|ddsrouter|dib_split_bridge'
SAFE=" "
pid=$$
while [ "$pid" -gt 1 ]; do
    SAFE="$SAFE$pid "
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    [ -z "$pid" ] && break
done
stale() {
    for p in $(pgrep -f "$PATTERNS" 2>/dev/null); do
        case "$SAFE" in *" $p "*) continue ;; esac
        echo "$p"
    done
}
N_STALE=$(stale | wc -l)
if [ "$N_STALE" -eq 0 ]; then
    echo -e "${GREEN}[OK] Không có tiến trình pipeline nào còn sót${NC}"
else
    echo -e "${YELLOW}[WARN] $N_STALE tiến trình còn sống từ lượt trước — chạy ./scripts/stop_pipeline.sh trước khi bật lại T1-T6${NC}"
    WARN=1
fi

# --- 2. Pipeline đã sống chưa? Nếu chưa, dừng ở đây (chưa tới lúc kiểm mục 3) ---
echo -e "\n--- 2. Pipeline (T1-T6) ---"
if [ -z "${ROS_DISTRO:-}" ]; then
    echo -e "${YELLOW}[SKIP] Chưa source ROS 2, không kiểm được topic${NC}"
    PIPELINE_UP=0
elif timeout 5 ros2 topic list 2>/dev/null | grep -qx '/mavros/state'; then
    echo -e "${GREEN}[OK] /mavros/state có mặt — pipeline đã lên${NC}"
    PIPELINE_UP=1
else
    echo -e "${YELLOW}[INFO] /mavros/state chưa có — pipeline chưa bật hoặc chưa xong.${NC}"
    echo "       Bật đủ T1-T6 (README.md mục 2.2) rồi chạy lại script này để kiểm mục 3."
    PIPELINE_UP=0
    WARN=1
fi

# --- 3. Ba mục kiểm trước bay (README.md §2.2 "Kiểm 3 thứ trước khi bay") ---
echo -e "\n--- 3. Kiểm trước bay ---"
if [ "$PIPELINE_UP" -eq 1 ]; then
    SIM_TIME=$(timeout 5 ros2 param get /mavros/mavros_node use_sim_time 2>/dev/null)
    if echo "$SIM_TIME" | grep -qi 'true'; then
        echo -e "${GREEN}[OK] use_sim_time = True${NC}"
    else
        echo -e "${RED}[FAIL] use_sim_time không phải True (đọc được: '$SIM_TIME').${NC}"
        echo "       Kiểm T4 dùng đúng sitl_mavros.launch.py, không phải 'mavros px4.launch' (Phụ lục A.6)"
        FAIL=1
    fi

    CTRL=$(timeout 5 ros2 control list_controllers 2>/dev/null)
    N_CTRL=$(echo "$CTRL" | grep -c .)
    N_ACTIVE=$(echo "$CTRL" | awk '{print $NF}' | grep -xc 'active')
    if [ "$N_CTRL" -eq 4 ] && [ "$N_ACTIVE" -eq 4 ]; then
        echo -e "${GREEN}[OK] ros2 control list_controllers: 4/4 active${NC}"
    else
        echo -e "${RED}[FAIL] Controller chưa đủ 4/4 active ($N_ACTIVE/$N_CTRL).${NC}"
        echo "       Xem T2 (box_spawn_only.launch.py) — Phụ lục A.5 nếu còn 'unconfigured'"
        FAIL=1
    fi

    MAVSTATE=$(timeout 5 ros2 topic echo --once /mavros/state 2>/dev/null)
    if echo "$MAVSTATE" | grep -q 'connected: true'; then
        echo -e "${GREEN}[OK] /mavros/state connected: true${NC}"
    else
        echo -e "${RED}[FAIL] MAVROS chưa connected tới PX4.${NC}"
        echo "       Kiểm T1 đã tới pxh> chưa, T4 đã lên chưa"
        FAIL=1
    fi
else
    echo "       (bỏ qua — xem mục 2 ở trên)"
fi

# --- Kết luận ---
echo
if [ "$FAIL" -ne 0 ]; then
    echo -e "${RED}=== NO-GO — sửa các mục [FAIL] ở trên rồi chạy lại ===${NC}"
    exit 1
elif [ "$WARN" -ne 0 ]; then
    echo -e "${YELLOW}=== Chưa đủ để chấm GO — xem các mục [WARN]/[INFO] ở trên ===${NC}"
    exit 1
else
    echo -e "${GREEN}=== GO — đủ điều kiện bay ===${NC}"
    exit 0
fi
