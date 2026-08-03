std_msgs/Header header
dib_msgs/State state
# --- REQ_UAV_FLY_0020: fallback / error reporting (additive) ---
uint32[] error                       # active error codes; empty = nominal
uint32 ERR_FALLBACK_LANDING = 2      # 0002: drone did a fallback (unsafe) landing
