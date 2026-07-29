#ifndef SECURING_STATE_MANAGER_HPP
#define SECURING_STATE_MANAGER_HPP

#include <iostream>

class BoxStateManager;

enum class SecuringState
{
    NONE,
    CHECK_POSITION,
    CLOSE_CLAPM_H,
    CLOSE_CLAPM_V,
    CLOSE_LID,
    WAITING_DRONE_REQUEST_POWER_OFF,
    POWER_OFF,
    DONE,
    FAILED
};

class SecuringStateManager
{
    public:
        SecuringStateManager(BoxStateManager* box_state_manager);
        void checkPosition();
        void closeClampH();
        void closeClampV();
        void powerOff();
        void closeLid();
        void waitingDroneRequestPowerOff();
        void done();
        void failed();
        void none();

        SecuringState checkNewState(SecuringState state); 
        void runStateMachine(SecuringState new_state);

        SecuringState state;
        BoxStateManager* box_state_manager;
        bool position_ok = false;
        bool clamp_h_closed = false;
        bool clamp_v_closed = false;
        bool lid_closed = false;
        double start_time;
        bool change_state = false;
        uint8_t cmd_success = 0; // 0: none, 1: success, 2: failed
};


#endif