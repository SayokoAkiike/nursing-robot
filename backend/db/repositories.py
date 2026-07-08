"""Persistence facade used by the services layer.
 
PR1 introduced this module as a thin wrapper over the JSON file storage in
`backend/storage.py`. This PR (PR2) replaces the internals with SQLAlchemy
against `care_requests` / `robot_events` -- callers (`workflow_service`,
`verification_service`) are unchanged, since they only ever depended on the
function signatures below, never on `backend/storage.py` directly. JSON file
storage is retired; `backend/storage.py` and its test are removed.
 
Still a single logical "current request" (see the note in
`api/routes_requests.py`): `save_state()` clears the table before inserting
the new row, exactly mirroring the JSON file's whole-file-overwrite
semantics. PR3 ("Task resource model") is what introduces true multiple
concurrent rows -- do not build multi-task assumptions on top of this
module until then.
"""
from backend.db.models import CareRequestRow, RobotEventRow
from backend.db.session import get_session, init_db
 
 
def _row_to_state(row) -> dict:
    if row is None:
        return {"request": None, "robot_state": "IDLE"}
    return {
        "request_id": row.request_id,
        "request_type": row.request_type,
        "request": row.request_label,
        "kit": row.kit,
        "risk": row.risk,
        "patient_id": row.patient_id,
        "robot_state": row.robot_state,
        "timestamp": row.timestamp,
    }
 
 
def load_state() -> dict:
    init_db()
    session = get_session()
    try:
        row = session.query(CareRequestRow).first()
        return _row_to_state(row)
    finally:
        session.close()
 
 
def save_state(state: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.query(CareRequestRow).delete()
        if state.get("request_id"):
            session.add(
                CareRequestRow(
                    request_id=state["request_id"],
                    request_type=state.get("request_type"),
                    request_label=state.get("request"),
                    kit=state.get("kit"),
                    risk=state.get("risk"),
                    patient_id=state.get("patient_id"),
                    robot_state=state.get("robot_state", "IDLE"),
                    timestamp=state.get("timestamp"),
                )
            )
        session.commit()
    finally:
        session.close()
 
 
def load_logs() -> list:
    init_db()
    session = get_session()
    try:
        rows = session.query(RobotEventRow).order_by(RobotEventRow.id).all()
        return [
            {
                "timestamp": r.timestamp,
                "event_type": r.event_type,
                "patient_id": r.patient_id,
                "request": r.request,
                "kit": r.kit,
                "previous_state": r.previous_state,
                "next_state": r.next_state,
                "result": r.result,
                "message": r.message,
            }
            for r in rows
        ]
    finally:
        session.close()
 
 
def append_log_entry(entry: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(
            RobotEventRow(
                request_id=entry.get("request_id"),
                timestamp=entry.get("timestamp", ""),
                event_type=entry.get("event_type", ""),
                patient_id=entry.get("patient_id"),
                request=entry.get("request"),
                kit=entry.get("kit"),
                previous_state=entry.get("previous_state"),
                next_state=entry.get("next_state"),
                result=entry.get("result"),
                message=entry.get("message"),
            )
        )
        session.commit()
    finally:
        session.close()
 
 
def list_requests() -> list:
    state = load_state()
    if state.get("robot_state", "IDLE") == "IDLE":
        return []
    return [state]
 
 
def get_request(request_id: str):
    state = load_state()
    if state.get("request_id") == request_id:
        return state
    return None
 
