"""Read-only domain registry endpoints (roadmap item 4): Hospital/Ward/
Room/Bed/Patient/Nurse/Robot. No auth on any of these, matching GET
/requests / GET /escalations's precedent of being a plain read-only view --
nothing here is a nurse-gated action.
"""
from fastapi import APIRouter

from backend.core.errors import NotFoundError
from backend.db import repositories
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
    return repositories.list_robots()


@router.get("/wards")
def list_wards():
    return domain_service.list_wards_view()
