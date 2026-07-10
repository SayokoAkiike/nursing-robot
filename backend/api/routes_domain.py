"""Read-only domain registry endpoints (roadmap item 4): Hospital/Ward/
Room/Bed/Patient/Nurse/Robot. No auth on any of these, matching GET
/requests / GET /escalations's precedent of being a plain read-only view --
nothing here is a nurse-gated action.
"""
from fastapi import APIRouter

from backend.core.errors import NotFoundError
from backend.services import domain_service

router = APIRouter(tags=["domain"])


@router.get("/patients")
def list_patients():
    return domain_service.list_patients_view()


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    view = domain_service.get_patient_view(patient_id)
    if view is None:
        raise NotFoundError(f"Patient {patient_id} not found")
    return view


@router.get("/robots")
def list_robots():
    """Item 5: each robot now also carries a live `status` (IDLE/BUSY),
    via `domain_service.list_robots_view()` -- previously just the static
    registry row (`repositories.list_robots()`), no status field."""
    return domain_service.list_robots_view()


@router.get("/wards")
def list_wards():
    return domain_service.list_wards_view()
