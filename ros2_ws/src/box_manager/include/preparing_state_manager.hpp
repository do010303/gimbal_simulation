#ifndef PREPARING_STATE_MANAGER_HPP
#define PREPARING_STATE_MANAGER_HPP


#include <dib_msgs/msg/lid_status.hpp>
#include <dib_msgs/msg/wind_sensor.hpp>
#include <dib_msgs/msg/rain.hpp>
#include <dib_msgs/msg/temperature.hpp>
#include <dib_msgs/msg/humidity.hpp>
#include <dib_msgs/srv/lid_cmd.hpp>
#include <dib_msgs/srv/cooling_cmd.hpp>
#include <dib_msgs/srv/charge_cmd.hpp>
#include <dib_msgs/srv/power_button_cmd.hpp>
#include <dib_msgs/srv/clamp_cmd.hpp>

enum class PreparingState
{
    NONE,
    CHECK_WEATHER_CONDITIONS,
    POWER_ON_DRONE,
    WAITING_DRONE_READY,
    OPEN_BOX_AND_CLAMP,
    WAITING_BOX_CLAMP_OPEN,
    WAITING_READY_TO_FLY,
    DONE,
    FAILED
};

enum class PreparingStateError
{
    NONE,
    WEATHER_CONDITIONS_FAIL,
    WAITING_DRONE_READY_TIMEOUT,
    CMD_OPEN_BOX_CLAMP_FAIL,
    POWER_ON_FAIL,
    WAITING_BOX_CLAMP_OPEN_TIMEOUT,
    WAITING_READY_TO_FLY_TIMEOUT,
};


class BoxStateManager;

class PreparingStateManager
{
    public:
        PreparingStateManager(BoxStateManager* box_state_manager);

        void checkWeatherConditions();
        void powerOnDrone();
        void waitingDroneReady();
        void openBoxAndClamp();
        void waitingBoxClampOpen();
        void waitingReadyToFly();
        void done();
        void failed();
        void none();

        PreparingState checkNewState(PreparingState state); 
        void runStateMachine(PreparingState new_state);

        PreparingState state;
        BoxStateManager* box_state_manager;
        bool weather_conditions_ok = false;
        bool drone_ready = false;
        bool box_clamp_open = false;
        bool box_open = false;
        uint8_t send_cmd_open_box_and_clamp = 0;                 // 1: success, 2: failed
        uint8_t send_cmd_power_on = 0;                         // 1: success, 2: failed
        bool waiting_timeout = false;
        double start_time;
        uint8_t change_state = false;
        PreparingStateError error = PreparingStateError::NONE;
};

#endif // PREPARING_STATE_MANAGER_HPP