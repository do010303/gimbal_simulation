uint8 lid_state
uint8 clamp_state
uint8 cooling_battery_state
float64 latitude
float64 longitude
float32 yaw
uint32 drone_id
uint32 box_id
int32[] error
# --- REQ_BOX_FEA_0003 spec-named fields (additive; mirror/extend the above) ---
uint8 status_door          # = lid_state, spec name (CLOSED/OPENED/CLOSING/OPENING)
uint8 status_hold          # = clamp_state, spec name
bool is_empty              # true = no drone in box (box_state == EMPTY)
bool connected             # box link to drone/server is up
uint8 air_conditioner      # 0 = off, 1 = on (spec: bật/tắt điều hòa)
uint8 CLOSED = 0
uint8 OPENED = 1
uint8 CLOSING = 2
uint8 OPENING = 3
uint8 AC_OFF = 0
uint8 AC_ON = 1
