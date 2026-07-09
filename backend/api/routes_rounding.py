"""Rounding session endpoints.

Unauthenticated, like `routes_requests.py` -- these represent the robot's
own actions as it rounds (starting a session, detecting a patient,
prompting for interaction, classifying a response) rather than a nurse
action. The one nurse-authenticated action related to rounding
(acknowledging an escalation) lives in `routes_escalations.py` instead,
mirroring how `routes_tasks.py` / `routes_verification.py` are the
nurse-authenticated counterpart to this file's `routes_requests.py`
sibling.
"""
from fastapi import APIRouter

from backend.schemas.rounding import (
    ClassifyNeedRequest,
    DetectPatientRequest,
    EscalateRequest,
    RequireDeliveryRequest,
    RoundingStart,
)
from backend.services import rounding_service

router = APIRouter(prefix="/rounding", tags=["rounding"])


@router.post("/start")
def start_rounding(body: RoundingStart):
    session = rounding_service.start_rounding(body.room, robot_id=body.robot_id)
    return {"rounding_session_id": session["id"], "status": session["status"]}


@router.get("/{session_id}")
def get_rounding_session(session_id: str):
    return rounding_service.get_session(session_id)


@router.post("/{session_id}/detect-patient")
def detect_patient(session_id: str, body: DetectPatientRequest):
    return rounding_service.detect_patient(session_id, body.patient_id)


@router.post("/{session_id}/start-interaction")
def start_interaction(session_id: str):
    result = rounding_service.start_interaction(session_id)
    return {"prompt": result["prompt"], **result["session"]}


@router.post("/{session_id}/classify-need")
def classify_need(session_id: str, body: ClassifyNeedRequest):
    result = rounding_service.classify_need(
        session_id, body.patient_response, input_mode=body.input_mode
    )
    return {
        "detected_need": result["detected_need"],
        "escalation_level": result["escalation_level"],
        "route": result["route"],
        "summary": result["summary"],
        "suggested_action": result["suggested_action"],
    }


@router.post("/{session_id}/provide-information")
def provide_information(session_id: str):
    """The INFORMATION_ONLY branch -- not in the proposal doc's section 5
    endpoint list, but needed to actually complete a session whose
    classify-need route came back INFORMATION_ONLY (see
    RequireDeliveryRequest's docstring in schemas/rounding.py for the
    same gap on the delivery side)."""
    return rounding_service.provide_information(session_id)


@router.post("/{session_id}/escalate")
def escalate(session_id: str, body: EscalateRequest):
    result = rounding_service.escalate(
        session_id,
        summary=body.summary,
        priority=body.priority,
        suggested_action=body.suggested_action,
        reason=body.reason,
        route=body.route,
    )
    return {"escalation_id": result["escalation_id"], **result["session"]}


@router.post("/{session_id}/require-delivery")
def require_delivery(session_id: str, body: RequireDeliveryRequest):
    result = rounding_service.require_delivery(
        session_id, body.request_type, patient_id=body.patient_id
    )
    return {"request_id": result["request_id"], **result["session"]}
