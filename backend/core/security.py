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
 
