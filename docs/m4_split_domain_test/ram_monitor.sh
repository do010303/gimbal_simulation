#!/usr/bin/env bash
# RAM monitor for the M4 split-domain pipeline.
#
# Samples every INTERVAL seconds and logs:
#   - system-wide used memory (from /proc/meminfo: MemTotal-MemAvailable)
#   - per-group RSS summed over the pipeline processes (PSS if available =
#     shared pages counted once, more honest for many ROS procs on one host)
#
# Groups: px4/gz sim, mavros, ros2 (all other ROS nodes), bridge (ddsrouter or
# dib_split_bridge — whichever M4 bridge is running).
#
# Usage:  ./ram_monitor.sh [INTERVAL_SEC] [OUT_CSV]
#   ./ram_monitor.sh                 # 2s, ram_monitor.csv, live table + CSV
#   ./ram_monitor.sh 5 /tmp/m4.csv   # 5s cadence, custom file
# Stop with Ctrl-C — it prints peak RAM for each group on exit.

set -u
INTERVAL="${1:-2}"
OUT="${2:-ram_monitor.csv}"

# Sum PSS (KB) for PIDs whose cmdline matches a regex. PSS needs root-readable
# /proc/<pid>/smaps_rollup; falls back to RSS from ps if PSS is unreadable.
have_pss=1
sum_kb() {
  local re="$1" total=0 rss_total=0 pid pss rss
  for pid in $(pgrep -f "$re" 2>/dev/null); do
    [ "$pid" = "$$" ] && continue
    if [ -r "/proc/$pid/smaps_rollup" ]; then
      pss=$(awk '/^Pss:/{s+=$2} END{print s+0}' "/proc/$pid/smaps_rollup" 2>/dev/null)
      total=$((total + pss))
    else
      have_pss=0
    fi
    rss=$(awk '/^VmRSS:/{print $2}' "/proc/$pid/status" 2>/dev/null)
    rss_total=$((rss_total + ${rss:-0}))
  done
  # prefer PSS when we could read it for everything, else RSS
  if [ "$have_pss" = 1 ] && [ "$total" -gt 0 ]; then echo "$total"; else echo "$rss_total"; fi
}

sys_used_kb() {
  awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2} END{print t-a}' /proc/meminfo
}

# regexes per group (px4 binary, gz sim, mavros node, bridge, then the rest of ros2)
RE_SIM='(bin/px4|gz sim|ruby.*gz|gzserver)'
RE_MAVROS='mavros_node'
# Matches BOTH M4 bridges: ddsrouter (mặc định) và dib_split_bridge (dự phòng).
# Chỉ một cái chạy tại một thời điểm nên cột bridge không bị cộng trùng.
RE_BRIDGE='(ddsrouter|dib_split_bridge)'
RE_ROS='(ros2|component_container|robot_state_publisher|_node|precision_landing|box_)'

echo "ts,sys_used_mb,sim_mb,mavros_mb,bridge_mb,ros_other_mb" | tee "$OUT"
peak_sys=0; peak_sim=0; peak_mav=0; peak_br=0; peak_ros=0

on_exit() {
  echo ""
  echo "=== PEAK (MB) ==============================="
  printf "system used : %d\n" "$peak_sys"
  printf "sim (px4/gz): %d\n" "$peak_sim"
  printf "mavros      : %d\n" "$peak_mav"
  printf "bridge      : %d\n" "$peak_br"
  printf "ros (other) : %d\n" "$peak_ros"
  echo "metric: $([ "$have_pss" = 1 ] && echo PSS || echo RSS) — log: $OUT"
  exit 0
}
trap on_exit INT TERM

while true; do
  ts=$(date +%H:%M:%S)
  sys=$(( $(sys_used_kb) / 1024 ))
  sim=$(( $(sum_kb "$RE_SIM") / 1024 ))
  mav=$(( $(sum_kb "$RE_MAVROS") / 1024 ))
  br=$((  $(sum_kb "$RE_BRIDGE") / 1024 ))
  ros=$(( $(sum_kb "$RE_ROS") / 1024 ))
  (( sys > peak_sys )) && peak_sys=$sys
  (( sim > peak_sim )) && peak_sim=$sim
  (( mav > peak_mav )) && peak_mav=$mav
  (( br  > peak_br  )) && peak_br=$br
  (( ros > peak_ros )) && peak_ros=$ros
  line="$ts,$sys,$sim,$mav,$br,$ros"
  echo "$line" >> "$OUT"
  printf "\r%s  sys=%-5d sim=%-5d mavros=%-4d bridge=%-3d ros=%-5d MB   " \
    "$ts" "$sys" "$sim" "$mav" "$br" "$ros"
  sleep "$INTERVAL"
done
