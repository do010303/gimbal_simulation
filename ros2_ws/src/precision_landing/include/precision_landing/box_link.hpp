#ifndef PRECISION_LANDING__BOX_LINK_HPP_
#define PRECISION_LANDING__BOX_LINK_HPP_

#include <string>
#include <memory>
#include <rclcpp/rclcpp.hpp>
#include <dib_msgs/msg/box_cmd.hpp>
#include <dib_msgs/msg/box_state.hpp>

namespace precision_landing
{

/**
 * @brief Drone-side link to the box FSM (box_manager::BoxStateManager).
 *
 * M3. Owns the BoxCmd topic publisher only; the box_state it reasons about is
 * pushed in by the controller's existing on_box_telemetry() callback rather
 * than re-subscribing to /b<box_id>/telemetry a second time. One subscription
 * feeds both the GOTO_BOX navigation path (box_lat_/box_lon_/box_yaw_, already
 * flight-tested) and this class, so there is no chance of the two disagreeing.
 *
 * M4: publishes on b<box_id>/drone_cmd (dib_msgs/BoxCmd) rather than calling
 * the b<box_id>/cmd SERVICE. DDS-Router (the M4 domain bridge candidate)
 * bridges topics correctly but drops service replies across domains -- and
 * the service reply was already unused here (see below), so this is a
 * behavior-preserving switch, not a functional change. box_state_manager's
 * b<box_id>/cmd service is untouched and still serves the operator/server
 * role (agent_id % 10 == 0); it now also subscribes to drone_cmd for the
 * drone role (agent_id % 10 == 2) that used to arrive only via the service.
 *
 * Contract verified against box_manager/src/box_state_manager.cpp:
 *  - Commands route on agent_id % 10: 0 = operator/server, 2 = drone. Only
 *    the drone branch accepts REQUEST_LANDING, and only while box_state ==
 *    EMPTY. It then derives drone_id_ = agent_id / 10.
 *    => agent_id = drone_id * 10 + AGENT_ROLE_DRONE.
 *  - After accepting, the box walks EMPTY -> IDLE -> PREPARING_FOR_LANDING ->
 *    WAITING_FOR_LANDING(7) on its own. State 7 is the "box is open, come
 *    down" signal that is_ready() reports.
 *  - No landed notification is needed from here: box_manager auto-transitions
 *    WAITING_FOR_LANDING -> SECURING_DRONE off d<drone_id>/telemetry, which
 *    the M2 mavros_to_dib_telemetry bridge publishes (proven by test 6b).
 */
class BoxLink
{
public:
  /// agent_id encoding expected by box_state_manager.cpp (agent_id % 10).
  static constexpr uint64_t AGENT_ROLE_DRONE = 2;

  BoxLink(rclcpp::Node * node, int box_id, int drone_id);

  /// Feed box_state from the controller's BoxTelemetry callback.
  void set_box_state(uint8_t state);

  /**
   * Publish BoxCmd{REQUEST_LANDING} once, then resend every REQUEST_RETRY_SEC
   * until is_ready() latches from telemetry. It is a plain topic publish (see
   * class docs) so there is no reply to gate on; the resend cadence is the
   * only thing standing in for the old service retry-on-rejection logic, and
   * telemetry was always the trustworthy signal anyway (is_ready()'s doc).
   * Safe to call every control-loop tick; never blocks (topic publish only).
   */
  void request_landing();

  /**
   * True once the box has reported WAITING_FOR_LANDING(7) at any point.
   *
   * Deliberately LATCHED, not a live equality test. The box does not stay in
   * state 7: box_state_manager moves on to SECURING_DRONE(8) as soon as it
   * sees the drone on the ground. A plain `box_state_ == 7` check can miss the
   * window if a telemetry sample is dropped (BoxTelemetry is a lossy stream)
   * and would then time out into FALLBACK even though the box had opened up
   * correctly. Same guard the box_hybrid_precision_lander.py prototype uses
   * (`box_ready_seen`).
   *
   * Call reset() when starting a new landing attempt so a stale latch from a
   * previous cycle cannot skip the wait.
   */
  bool is_ready() const;

  /**
   * M3.6. Publish BoxCmd{TURN_OFF_DRONE} once the drone is down and secured,
   * so the box can finish SECURING_DRONE and move on to CHARGING.
   *
   * Idempotent and retried like request_landing(), and additionally GATED on
   * box_state == SECURING_DRONE: box_state_manager.cpp only looks at this
   * command in that state, so sending it earlier is silently dropped.
   *
   * The box stores it as a sticky flag (request_poweroff) that its securing
   * sub-FSM consumes when it reaches WAITING_DRONE_REQUEST_POWER_OFF, which is
   * ~35 s after touchdown (clamps then lid must close first). So the command
   * may be sent well before it is acted on; that is expected.
   */
  void request_power_off();

  /**
   * True once the box has left SECURING_DRONE for CHARGING.
   *
   * This is the ONLY confirmation available, by design: it was already true
   * before the M4 topic switch, since box_state_manager::box_cmd_callback()
   * set response->success = true unconditionally on its first line and then
   * handed the work to a detached thread, so the old service reply was sent
   * before anything was evaluated and carried no information either.
   * Telemetry is, and always was, the real contract.
   */
  bool power_off_confirmed() const {return power_off_confirmed_;}

  /// Clear the ready latch and the request guards for a fresh landing attempt.
  void reset();

  /**
   * True once REQUEST_LANDING has been published at least once.
   *
   * Diagnostic only (logged alongside box_state() in WAIT_BOX_READY) -- there
   * is no reply to a topic publish, so this cannot mean "the box agreed"; it
   * never meant that even pre-M4 (see power_off_confirmed()'s doc). Real
   * acceptance shows up as the box leaving EMPTY, which is_ready() latches.
   */
  bool landing_request_accepted() const {return request_sent_;}

  /// True if a box_state has ever been received.
  bool has_box_state() const {return has_box_state_;}

  uint8_t box_state() const {return box_state_;}

  int box_id() const {return box_id_;}
  int drone_id() const {return drone_id_;}

private:
  rclcpp::Node * node_;
  int box_id_;
  int drone_id_;

  rclcpp::Publisher<dib_msgs::msg::BoxCmd>::SharedPtr pub_cmd_;

  uint8_t box_state_{dib_msgs::msg::BoxState::EMPTY};
  bool has_box_state_{false};
  bool box_ready_latched_{false};

  bool request_sent_{false};
  double last_request_time_{0.0};

  bool power_off_sent_{false};
  bool power_off_confirmed_{false};
  double last_power_off_time_{0.0};

  /// Resend a command until telemetry confirms it landed (no reply to a
  /// topic publish, so this is the only retry signal available).
  static constexpr double REQUEST_RETRY_SEC = 3.0;

  double now_sec() const;
};

}  // namespace precision_landing

#endif  // PRECISION_LANDING__BOX_LINK_HPP_
