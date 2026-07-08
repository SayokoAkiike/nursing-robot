"""Backward-compat shim.
 
The state machine now lives in `backend/services/robot_service.py` (see that
module's docstring for why it was consolidated from two disagreeing
implementations into one). Kept here because
`ui/nurse_dashboard/app.py` still imports from this path; will be removed
once the UI is updated to import from `backend.services.robot_service`
directly (tracked as a follow-up, out of scope for the backend cleanup PR).
"""
from backend.services.robot_service import (  # noqa: F401
    ALLOWED_TRANSITIONS,
    DISPLAY_FLOW,
    STATE_LABELS,
    STATE_MESSAGES,
    RobotState,
    RobotStateMachine,
    allowed_next_state,
    is_valid_transition,
    verify_transition,
)
 
if __name__ == "__main__":
    from backend.services.robot_service import RobotStateMachine as _Demo  # noqa
 
    import runpy
 
    runpy.run_module("backend.services.robot_service", run_name="__main__")
 
