#!/bin/bash
# Script verify_build_env.sh - Kiểm tra môi trường build và cài đặt dependency tự động

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0;0m'

echo -e "${GREEN}=== KIỂM TRA MÔI TRƯỜNG DỰ ÁN PRECISION LANDING ===${NC}\n"

# 1. Kiểm tra ROS 2
if [ -z "$ROS_DISTRO" ]; then
    echo -e "${RED}[FAIL] Chưa source ROS 2!${NC} Vui lòng chạy: source /opt/ros/humble/setup.bash"
    exit 1
else
    echo -e "${GREEN}[OK] Đã tìm thấy ROS 2: $ROS_DISTRO${NC}"
fi

# 2. Kiểm tra colcon
if ! command -v colcon &> /dev/null; then
    echo -e "${YELLOW}[WARN] Thiếu colcon build tool!${NC} Đang cài đặt..."
    sudo apt update && sudo apt install -y python3-colcon-common-extensions
else
    echo -e "${GREEN}[OK] Đã cài đặt colcon${NC}"
fi

# 3. Kiểm tra OpenCV
if python3 -c "import cv2" &> /dev/null; then
    OPENCV_VER=$(python3 -c "import cv2; print(cv2.__version__)")
    echo -e "${GREEN}[OK] Đã tìm thấy OpenCV qua Python (Version: $OPENCV_VER)${NC}"
else
    echo -e "${YELLOW}[WARN] Thiếu python3-opencv!${NC} Đang cài đặt..."
    sudo apt update && sudo apt install -y python3-opencv
fi

# 4. Kiểm tra MAVROS và các ROS 2 packages
MISSING_PKGS=()
check_ros_pkg() {
    if ! ros2 pkg list 2>/dev/null | grep "$1" &> /dev/null; then
        MISSING_PKGS+=("$2")
    fi
}


echo "Kiểm tra các gói ROS 2 cần thiết..."
check_ros_pkg "mavros" "ros-humble-mavros ros-humble-mavros-extras"
check_ros_pkg "cv_bridge" "ros-humble-cv-bridge"
check_ros_pkg "image_transport" "ros-humble-image-transport"
check_ros_pkg "rqt_image_view" "ros-humble-rqt-image-view"

# Kiểm tra Gazebo bridge (Harmonic hoặc Garden)
GZ_BRIDGE_INSTALLED=0
if ros2 pkg list 2>/dev/null | grep -E "(ros_gz_bridge|ros_gzharmonic_bridge)" &> /dev/null; then
    echo -e "${GREEN}[OK] Đã cài đặt Gazebo Bridge${NC}"
    GZ_BRIDGE_INSTALLED=1
fi

if [ ${#MISSING_PKGS[@]} -ne 0 ] || [ $GZ_BRIDGE_INSTALLED -eq 0 ]; then
    echo -e "${YELLOW}[WARN] Thiếu một số gói ROS 2!${NC} Đang tự động cài đặt các gói thiếu..."
    sudo apt update
    if [ ${#MISSING_PKGS[@]} -ne 0 ]; then
        sudo apt install -y "${MISSING_PKGS[@]}"
    fi
    if [ $GZ_BRIDGE_INSTALLED -eq 0 ]; then
        # Kiểm tra phiên bản Gazebo để quyết định bridge
        if command -v gz &> /dev/null && gz sim --version | grep -q "Harmonic"; then
            echo "Đang cài đặt bridge cho Gazebo Harmonic..."
            sudo apt install -y ros-humble-ros-gzharmonic-bridge ros-humble-ros-gzharmonic-image
        else
            echo "Đang cài đặt bridge cho Gazebo Garden..."
            sudo apt install -y ros-humble-ros-gz-bridge ros-humble-ros-gz-image
        fi
    fi
else
    echo -e "${GREEN}[OK] Đã cài đặt đầy đủ tất cả gói ROS 2 cần thiết${NC}"
fi

# 5. Kiểm tra libaruco (ArUco C++)
echo "Kiểm tra thư viện ArUco C++ (libaruco.so)..."
ARUCO_LIB=$(find /usr/lib /usr/local/lib $HOME/.local/lib -name "libaruco.so*" 2>/dev/null | head -n 1)

if [ -z "$ARUCO_LIB" ]; then
    echo -e "${RED}[FAIL] Không tìm thấy thư viện libaruco.so!${NC}"
    echo -e "${YELLOW}Đang tự động giải nén và build ArUco 3.1.12 từ file đính kèm...${NC}"
    
    cd "$(dirname "$0")"
    if [ -f "aruco_build/aruco.zip" ]; then
        mkdir -p third_party
        cp aruco_build/aruco.zip third_party/
        cd third_party
        unzip -q -o aruco.zip
        cd aruco-3.1.12
        mkdir -p build
        cd build
        cmake .. \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_INSTALL_PREFIX=$HOME/.local \
          -DBUILD_UTILS=OFF \
          -DBUILD_GLSAMPLES=OFF \
          -DINSTALL_DOC=OFF
        make -j$(nproc)
        make install
        echo -e "${GREEN}[SUCCESS] Đã cài đặt libaruco thành công vào $HOME/.local!${NC}"
        cd ../../..
    else
        echo -e "${RED}[ERROR] Không tìm thấy file zip aruco_build/aruco.zip! Vui lòng kiểm tra lại cấu trúc repo.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[OK] Đã tìm thấy libaruco tại: $ARUCO_LIB${NC}"
fi

# 6. Kiểm tra Python requirements
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Kiểm tra các thư viện Python..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip3 install -r "$SCRIPT_DIR/requirements.txt"
    echo -e "${GREEN}[OK] Đã cài đặt các thư viện Python${NC}"
else
    pip3 install numpy pymavlink opencv-python
fi

# 7. Giải nén mesh visual thân box.
# BOX PAD1.0_simple.dae (270 MB) vượt giới hạn 100 MB của GitHub nên repo chỉ
# ship bản .gz (64 MB); URDF của box tham chiếu bản .dae, phải giải nén trước build.
echo "Kiểm tra mesh thân box (BOX PAD1.0_simple.dae)..."
BOX_DAE="$SCRIPT_DIR/ros2_ws/src/box_simulation/meshes/dae/BOX PAD1.0_simple.dae"
if [ -f "$BOX_DAE" ]; then
    echo -e "${GREEN}[OK] Mesh thân box đã sẵn sàng${NC}"
elif [ -f "$BOX_DAE.gz" ]; then
    echo -e "${YELLOW}Đang giải nén mesh thân box từ .gz...${NC}"
    gunzip -k "$BOX_DAE.gz"
    echo -e "${GREEN}[OK] Đã giải nén BOX PAD1.0_simple.dae${NC}"
else
    echo -e "${RED}[FAIL] Thiếu cả BOX PAD1.0_simple.dae lẫn .gz!${NC} Kiểm tra ros2_ws/src/box_simulation/meshes/dae/"
fi

# 8. Kiểm tra dependency NGOÀI repo — thiếu thì clone-and-run sẽ gãy im lặng.
echo "Kiểm tra dependency ngoài repo..."
DEP_FAIL=0
# 8a. Hai package box đã vendor phải có thật (không phải symlink gãy sau clone).
for pkg in box_manager box_simulation; do
    if [ ! -f "$SCRIPT_DIR/ros2_ws/src/$pkg/package.xml" ]; then
        echo -e "${RED}[FAIL] Thiếu package '$pkg' trong ros2_ws/src (không đọc được package.xml).${NC}"
        DEP_FAIL=1
    fi
done
[ $DEP_FAIL -eq 0 ] && echo -e "${GREEN}[OK] box_manager và box_simulation đã có trong repo${NC}"
DEP_WARN=0
# 8b. gz_ros2_control (Harmonic) — bắt buộc cho ros2_control của box.
if ! ros2 pkg list 2>/dev/null | grep -qx "gz_ros2_control"; then
    echo -e "${YELLOW}[WARN] Chưa thấy gz_ros2_control trong môi trường ROS.${NC}"
    echo    "       Build từ nguồn cho Gazebo Harmonic rồi source trước khi chạy box:"
    echo    "         source ~/gz_ros2_control_ws/install/setup.bash"
    echo    "       (bản apt ros-humble-gz-ros2-control là cho Fortress → gz server segfault khi spawn box)"
    DEP_WARN=1
fi
# 8c. px4_msgs — clone riêng (giữ nguyên cơ chế cũ). Chỉ 'px4_offboard' (pipeline
# legacy mục 3) import nó lúc CHẠY; build vẫn xanh khi thiếu, và pipeline
# drone-in-a-box M3 không dùng tới.
if [ ! -f "$SCRIPT_DIR/ros2_ws/src/px4_msgs/package.xml" ]; then
    echo -e "${YELLOW}[WARN] Thiếu px4_msgs${NC} → 'px4_offboard' vẫn build được nhưng lỗi lúc chạy (M3 không cần)."
    echo    "         git clone https://github.com/PX4/px4_msgs.git \"$SCRIPT_DIR/ros2_ws/src/px4_msgs\""
    DEP_WARN=1
fi

# 9. Camera gimbal — FOV quyết định cấu hình đã đo ra M3 PASS 8/8.
GIMBAL_SDF="$HOME/PX4/Tools/simulation/gz/models/gimbal/model.sdf"
if [ -f "$GIMBAL_SDF" ]; then
    if grep -q "<horizontal_fov>1.4137</horizontal_fov>" "$GIMBAL_SDF"; then
        echo -e "${GREEN}[OK] Camera gimbal đúng FOV 1.4137 rad (81°)${NC}"
    else
        echo -e "${YELLOW}[WARN] Camera gimbal KHÔNG phải FOV 1.4137 rad.${NC} Chạy lại bước rsync overlay:"
        echo    "         cd ~/PX4 && rsync -a examples/SITL_PrecisionLanding/px4/Tools/simulation/gz/ Tools/simulation/gz/"
        DEP_WARN=1
    fi
else
    echo -e "${YELLOW}[WARN] Không thấy $GIMBAL_SDF${NC} — kiểm tra cây PX4 và bước rsync overlay."
    DEP_WARN=1
fi

if [ $DEP_FAIL -ne 0 ]; then
    echo -e "\n${RED}=== CÓ LỖI [FAIL]: sửa xong rồi hãy build. ===${NC}"
    exit 1
elif [ $DEP_WARN -ne 0 ]; then
    echo -e "\n${YELLOW}=== XONG, NHƯNG CÒN [WARN] ở trên — đọc và xử lý trước khi build. ===${NC}"
else
    echo -e "\n${GREEN}=== XÁC THỰC HOÀN TẤT: Môi trường đã sẵn sàng để build! ===${NC}"
fi
echo -e "Hãy chạy lệnh sau để build dự án:"
echo -e "  cd ros2_ws && colcon build --symlink-install"
