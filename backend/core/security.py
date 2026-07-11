import hmac

from fastapi import Header, HTTPException

from backend.core.config import get_settings


def require_nurse(x_nurse_token: str = Header(default="")) -> None:
    """FastAPI dependency guarding nurse-only actions.

    Uses a constant-time comparison instead of `==` to avoid a (low-severity,
    but free-to-fix) timing side channel on the static token.
    """
    settings = get_settings()
    token = settings.require_nurse_token()
    if not hmac.compare_digest(x_nurse_token, token):
        raise HTTPException(status_code=401, detail="Nurse token required")


def require_robot(x_robot_token: str = Header(default="")) -> None:
    """FastAPI dependency guarding robot/sensor-originated writes that
    have no state-machine gate of their own -- currently just
    POST /escalations/vision-report. See Settings.robot_token's
    docstring in backend/core/config.py for why this endpoint
    specifically needed its own token rather than staying
    unauthenticated like /rounding/*."""
    settings = get_settings()
    token = settings.require_robot_token()
    if not hmac.compare_digest(x_robot_token, token):
        raise HTTPException(status_code=401, detail="Robot token required")

