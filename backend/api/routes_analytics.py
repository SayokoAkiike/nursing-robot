"""Read-only analytics endpoints (PR10, PR11).

Unauthenticated like the other GET-only routes (`routes_logs.py`) -- these
expose aggregate counts, not per-patient data, so the same trust boundary
as the rest of the read surface applies. If per-patient detail is ever
added here, it should get the same `require_nurse` dependency
`routes_tasks.py` uses.
"""
from fastapi import APIRouter

from backend.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def get_summary():
    return analytics_service.summary()


@router.get("/verification-failures")
def get_verification_failures():
    return analytics_service.verification_failures()


@router.get("/state-durations")
def get_state_durations():
    return analytics_service.state_durations()


@router.get("/rounding-summary")
def get_rounding_summary():
    return analytics_service.rounding_summary()


@router.get("/escalation-breakdown")
def get_escalation_breakdown():
    return analytics_service.escalation_breakdown()
