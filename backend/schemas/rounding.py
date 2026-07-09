from pydantic import BaseModel

from backend.services.rounding_service import DEFAULT_ROBOT_ID


class RoundingStart(BaseModel):
    room: str
    robot_id: str = DEFAULT_ROBOT_ID


class DetectPatientRequest(BaseModel):
    patient_id: str


class ClassifyNeedRequest(BaseModel):
    patient_response: str
    input_mode: str = "simulated"


class EscalateRequest(BaseModel):
    summary: str
    priority: str
    suggested_action: str | None = None
    reason: str | None = None
    # Not in the original proposal doc's request body example, but
    # rounding_service.escalate() needs to know which NEED_CLASSIFIED
    # branch this is (NURSE_NOTIFICATION vs URGENT_ESCALATION -- both
    # currently land on ESCALATING_TO_NURSE, see
    # backend/services/robot_service.py's ROUNDING_BRANCH_TARGETS).
    # Defaults to the more common case so existing callers following the
    # doc's example body still work unchanged.
    route: str = "NURSE_NOTIFICATION"


class RequireDeliveryRequest(BaseModel):
    """PR24 addition beyond the proposal doc's section 5 endpoint list:
    the doc's classify-need response can return route="DELIVERY_REQUIRED",
    but no endpoint to act on that route was specified. Without this,
    there would be no way to reach rounding_service.require_delivery()
    from the API at all."""

    request_type: str
    patient_id: str | None = None


class AckRequest(BaseModel):
    acknowledged_by: str
