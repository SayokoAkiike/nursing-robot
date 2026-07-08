"""Backward-compat shim.
 
Domain constants now live in `backend/core/config.py`. Kept here because
`ui/patient_request_app/app.py` still imports from this path; will be
removed once the UI is updated to import from `backend.core.config`
directly (tracked as a follow-up, out of scope for the backend cleanup PR).
"""
from backend.core.config import (  # noqa: F401
    DEFAULT_PATIENT_ID,
    KIT_NAMES,
    PATIENTS,
    REQUEST_TYPES,
)
 
