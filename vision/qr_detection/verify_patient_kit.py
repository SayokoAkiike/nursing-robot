"""Backward-compat shim.
 
Verification logic now lives in `backend/services/verification_service.py`.
Kept here because `tests/test_verify_patient_kit.py` and the perception
module (PR4) reference this path; will be folded into `perception/` in a
later PR.
"""
from backend.services.verification_service import verify  # noqa: F401
 
