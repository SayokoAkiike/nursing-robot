"""Persistence facade used by the services layer.

PR1/PR2 had this module own the "current state" concept (a single
dict-shaped row). PR3 ("Task resource model") replaces that with plain CRUD
over the three real tables in `backend/db/models.py` --
`backend.services.workflow_service` now owns joining/merging rows into the
dict shape the API and tests expect; this module just persists and fetches
rows.
"""
from backend.db.models import (
    CareRequestRow,
    KitVerificationRow,
    RobotEventRow,
    RobotTaskRow,
    TaskStateTransitionRow,
)
from backend.db.session import get_session, init_db

# States that free up the robot for a new request (mirrors the old JSON
# singleton's `create_request` guard: `robot_state not in ["IDLE",
# "COMPLETED", "ERROR"]` raised ConflictError). Note ERROR does *not* block
# a new request -- that was true of the old code too.
NON_BLOCKING_TASK_STATES = {"IDLE", "COMPLETED", "ERROR"}

# States hidden from `list_active_tasks()` / GET /requests. Mirrors the old
# JSON singleton's `load_requests`, which only hid IDLE -- COMPLETED and
# ERROR tasks stayed visible (so a nurse can see and act on an errored
# task) until something resets them.
HIDDEN_FROM_LIST_STATES = {"IDLE"}


def _as_dict(row, fields) -> dict:
    return {f: getattr(row, f) for f in fields}


CARE_REQUEST_FIELDS = ["id", "patient_id", "request_type", "priority", "status", "created_at", "completed_at"]
ROBOT_TASK_FIELDS = ["id", "request_id", "robot_id", "state", "kit_id", "assigned_at", "updated_at"]


# ---- care_requests ---------------------------------------------------------

def insert_care_request(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(CareRequestRow(**row))
        session.commit()
    finally:
        session.close()


def get_care_request(request_id: str) -> dict | None:
    init_db()
    session = get_session()
    try:
        row = session.get(CareRequestRow, request_id)
        return _as_dict(row, CARE_REQUEST_FIELDS) if row else None
    finally:
        session.close()


def update_care_request_status(request_id: str, status: str, completed_at: str | None = None) -> None:
    init_db()
    session = get_session()
    try:
        row = session.get(CareRequestRow, request_id)
        if row is not None:
            row.status = status
            if completed_at is not None:
                row.completed_at = completed_at
            session.commit()
    finally:
        session.close()


# ---- robot_tasks ------------------------------------------------------------

def insert_robot_task(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(RobotTaskRow(**row))
        session.commit()
    finally:
        session.close()


def get_task_by_request_id(request_id: str) -> dict | None:
    init_db()
    session = get_session()
    try:
        row = session.query(RobotTaskRow).filter_by(request_id=request_id).first()
        return _as_dict(row, ROBOT_TASK_FIELDS) if row else None
    finally:
        session.close()


def get_active_task_for_robot(robot_id: str) -> dict | None:
    """The task (if any) currently occupying this robot -- state not in
    NON_BLOCKING_TASK_STATES. This is the per-robot concurrency guard: at
    most one such row may exist per robot_id at a time (enforced in
    workflow_service.create_request, not by a DB constraint yet)."""
    init_db()
    session = get_session()
    try:
        row = (
            session.query(RobotTaskRow)
            .filter(RobotTaskRow.robot_id == robot_id)
            .filter(RobotTaskRow.state.notin_(NON_BLOCKING_TASK_STATES))
            .first()
        )
        return _as_dict(row, ROBOT_TASK_FIELDS) if row else None
    finally:
        session.close()


def update_task_state(task_id: str, state: str, updated_at: str) -> None:
    init_db()
    session = get_session()
    try:
        row = session.get(RobotTaskRow, task_id)
        if row is not None:
            row.state = state
            row.updated_at = updated_at
            session.commit()
    finally:
        session.close()


def list_active_tasks() -> list:
    """Tasks visible in GET /requests -- hides IDLE only (see
    HIDDEN_FROM_LIST_STATES)."""
    init_db()
    session = get_session()
    try:
        rows = (
            session.query(RobotTaskRow)
            .filter(RobotTaskRow.state.notin_(HIDDEN_FROM_LIST_STATES))
            .order_by(RobotTaskRow.assigned_at)
            .all()
        )
        return [_as_dict(r, ROBOT_TASK_FIELDS) for r in rows]
    finally:
        session.close()


# ---- kit_verifications ------------------------------------------------------

def insert_kit_verification(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(KitVerificationRow(**row))
        session.commit()
    finally:
        session.close()


def list_kit_verifications_for_task(task_id: str) -> list:
    init_db()
    session = get_session()
    try:
        rows = (
            session.query(KitVerificationRow)
            .filter_by(task_id=task_id)
            .order_by(KitVerificationRow.id)
            .all()
        )
        return [
            {
                "task_id": r.task_id,
                "patient_id": r.patient_id,
                "kit_id": r.kit_id,
                "expected_patient_id": r.expected_patient_id,
                "scanned_patient_id": r.scanned_patient_id,
                "expected_kit_id": r.expected_kit_id,
                "scanned_kit_id": r.scanned_kit_id,
                "result": r.result,
                "message": r.message,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    finally:
        session.close()


# ---- task_state_transitions (PR8) -------------------------------------------

TASK_STATE_TRANSITION_FIELDS = [
    "id",
    "task_id",
    "request_id",
    "from_state",
    "to_state",
    "trigger_type",
    "triggered_by",
    "reason",
    "occurred_at",
]


def insert_task_state_transition(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(TaskStateTransitionRow(**row))
        session.commit()
    finally:
        session.close()


def list_task_state_transitions(task_id: str | None = None, request_id: str | None = None) -> list:
    """Ordered (oldest first) transition history, optionally filtered.

    Used directly by tests/PR9 audit checks, and by PR11's
    /analytics/state-durations, which needs the full ordered history per
    task to compute how long each state was occupied.
    """
    init_db()
    session = get_session()
    try:
        query = session.query(TaskStateTransitionRow)
        if task_id is not None:
            query = query.filter_by(task_id=task_id)
        if request_id is not None:
            query = query.filter_by(request_id=request_id)
        rows = query.order_by(TaskStateTransitionRow.id).all()
        return [_as_dict(r, TASK_STATE_TRANSITION_FIELDS) for r in rows]
    finally:
        session.close()


# ---- robot_events (unchanged from PR2) --------------------------------------

def append_log_entry(entry: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(
            RobotEventRow(
                request_id=entry.get("request_id"),
                task_id=entry.get("task_id"),
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
