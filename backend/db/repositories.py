"""Persistence facade used by the services layer.

PR1/PR2 had this module own the "current state" concept (a single
dict-shaped row). PR3 ("Task resource model") replaces that with plain CRUD
over the three real tables in `backend/db/models.py` --
`backend.services.workflow_service` now owns joining/merging rows into the
dict shape the API and tests expect; this module just persists and fetches
rows.
"""
from datetime import datetime, timedelta

from backend.db.models import (
    CareRequestRow,
    KitVerificationRow,
    NurseEscalationRow,
    PatientInteractionRow,
    RobotEventRow,
    RobotTaskRow,
    RoundingSessionRow,
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


# NOTE (PR22): `care_requests` gained `source` / `rounding_session_id`
# columns (backend/db/models.py) but they are deliberately *not* listed
# here yet. `tests/test_repositories.py::test_insert_and_get_care_request`
# asserts `get_care_request(...)` equals a REQUEST_ROW fixture with no
# such keys; adding them here would require every existing caller of
# `insert_care_request` to start passing them too. PR23 (which actually
# reads/writes these columns from `rounding_service`) extends this list
# and updates that fixture together, as one contained change.
CARE_REQUEST_FIELDS = ["id", "patient_id", "request_type", "priority", "status", "created_at", "completed_at"]
ROBOT_TASK_FIELDS = ["id", "request_id", "robot_id", "state", "kit_id", "assigned_at", "updated_at"]
KIT_VERIFICATION_FIELDS = [
    "id",
    "task_id",
    "patient_id",
    "kit_id",
    "expected_patient_id",
    "scanned_patient_id",
    "expected_kit_id",
    "scanned_kit_id",
    "result",
    "message",
    "created_at",
]


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


def update_care_request_status(request_id: str, status: str, completed_at: "datetime | None" = None) -> None:
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


def list_all_care_requests() -> list:
    """Every care_requests row, unfiltered (PR10: analytics aggregation).

    Small-scale (demo/portfolio) data volume -- aggregation happens in
    Python in `analytics_service`, not via SQL GROUP BY, so this just
    hands back every row.
    """
    init_db()
    session = get_session()
    try:
        rows = session.query(CareRequestRow).all()
        return [_as_dict(r, CARE_REQUEST_FIELDS) for r in rows]
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


def update_task_state(task_id: str, state: str, updated_at: "datetime") -> None:
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


def list_all_robot_tasks() -> list:
    """Every robot_tasks row, unfiltered (PR10: analytics aggregation)."""
    init_db()
    session = get_session()
    try:
        rows = session.query(RobotTaskRow).all()
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


def list_all_kit_verifications() -> list:
    """Every kit_verifications row, unfiltered (PR10: analytics aggregation)."""
    init_db()
    session = get_session()
    try:
        rows = session.query(KitVerificationRow).order_by(KitVerificationRow.id).all()
        return [_as_dict(r, KIT_VERIFICATION_FIELDS) for r in rows]
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
                timestamp=entry.get("timestamp"),
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


# ---- demo data lifecycle (PR12) ---------------------------------------------
#
# Used only by backend/scripts/seed_demo_data.py and reset_demo_data.py --
# nothing in the API or services layer calls these. Kept here rather than in
# the scripts themselves so they follow the same "scripts don't talk to the
# ORM directly" rule as everything else in this codebase.

def _shift_timestamp(value: "datetime | None", delta_seconds: float) -> "datetime | None":
    """Shift a stored timestamp by delta_seconds.

    PR15: all timestamp columns are now DateTime, so this is a plain
    datetime arithmetic helper -- the old dual-string-format handling
    (isoformat() vs strftime("%Y-%m-%d %H:%M:%S")) is gone because both
    formats no longer exist; every column round-trips through SQLAlchemy's
    DateTime type as a real datetime object.
    """
    if value is None:
        return None
    return value + timedelta(seconds=delta_seconds)


def shift_timestamps_for_request(request_id: str, delta_seconds: float) -> None:
    """Backdate (or postdate) every row belonging to one request_id by the
    same delta_seconds.

    Shifting every related row by an identical amount preserves every
    duration and ordering *within* that request exactly as it really
    happened when generated -- only which real-world day it appears to have
    happened on changes. This is what lets seed_demo_data.py spread
    synthetic requests across a `--days` window without fabricating
    internally-inconsistent timestamps.
    """
    init_db()
    session = get_session()
    try:
        care_request = session.get(CareRequestRow, request_id)
        if care_request is not None:
            care_request.created_at = _shift_timestamp(care_request.created_at, delta_seconds)
            care_request.completed_at = _shift_timestamp(care_request.completed_at, delta_seconds)

        task = session.query(RobotTaskRow).filter_by(request_id=request_id).first()
        if task is not None:
            task.assigned_at = _shift_timestamp(task.assigned_at, delta_seconds)
            task.updated_at = _shift_timestamp(task.updated_at, delta_seconds)

        if task is not None:
            for kv in session.query(KitVerificationRow).filter_by(task_id=task.id).all():
                kv.created_at = _shift_timestamp(kv.created_at, delta_seconds)

        for transition in session.query(TaskStateTransitionRow).filter_by(request_id=request_id).all():
            transition.occurred_at = _shift_timestamp(transition.occurred_at, delta_seconds)

        for event in session.query(RobotEventRow).filter_by(request_id=request_id).all():
            event.timestamp = _shift_timestamp(event.timestamp, delta_seconds)

        session.commit()
    finally:
        session.close()


# ---- rounding_sessions / patient_interactions / nurse_escalations (PR22) ---
#
# Plain CRUD, same shape as every table above: services layer (PR23's
# rounding_service) owns joining/interpreting these rows; this module just
# persists and fetches them.

ROUNDING_SESSION_FIELDS = [
    "id",
    "robot_id",
    "room",
    "patient_id",
    "status",
    "started_at",
    "ended_at",
    "interaction_summary",
    "detected_need",
    "escalation_level",
    "created_at",
    "updated_at",
]

PATIENT_INTERACTION_FIELDS = [
    "id",
    "rounding_session_id",
    "patient_id",
    "room",
    "prompt",
    "patient_response",
    "input_mode",
    "detected_need",
    "confidence",
    "created_at",
]

NURSE_ESCALATION_FIELDS = [
    "id",
    "rounding_session_id",
    "request_id",
    "patient_id",
    "room",
    "summary",
    "priority",
    "reason",
    "suggested_action",
    "status",
    "created_at",
    "acknowledged_at",
    "acknowledged_by",
]


def insert_rounding_session(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(RoundingSessionRow(**row))
        session.commit()
    finally:
        session.close()


def get_rounding_session(session_id: str) -> dict | None:
    init_db()
    session = get_session()
    try:
        row = session.get(RoundingSessionRow, session_id)
        return _as_dict(row, ROUNDING_SESSION_FIELDS) if row else None
    finally:
        session.close()


def update_rounding_session(
    session_id: str,
    *,
    status: str | None = None,
    patient_id: str | None = None,
    interaction_summary: str | None = None,
    detected_need: str | None = None,
    escalation_level: str | None = None,
    ended_at: "datetime | None" = None,
    updated_at: "datetime | None" = None,
) -> None:
    """Partial update -- only fields explicitly passed (non-None) are
    written. Mirrors `update_task_state`'s style but for the several
    optional fields a rounding session accumulates as it progresses."""
    init_db()
    session = get_session()
    try:
        row = session.get(RoundingSessionRow, session_id)
        if row is None:
            return
        if status is not None:
            row.status = status
        if patient_id is not None:
            row.patient_id = patient_id
        if interaction_summary is not None:
            row.interaction_summary = interaction_summary
        if detected_need is not None:
            row.detected_need = detected_need
        if escalation_level is not None:
            row.escalation_level = escalation_level
        if ended_at is not None:
            row.ended_at = ended_at
        if updated_at is not None:
            row.updated_at = updated_at
        session.commit()
    finally:
        session.close()


def list_active_rounding_sessions(robot_id: str | None = None) -> list:
    """Rounding sessions not yet COMPLETED/ERROR, optionally filtered by
    robot. Mirrors `get_active_task_for_robot`'s per-robot concurrency
    query, but returns a list (a robot could in principle have more than
    one open session across rooms is *not* assumed here -- callers in
    PR23's rounding_service enforce any single-active-session rule)."""
    init_db()
    session = get_session()
    try:
        query = session.query(RoundingSessionRow).filter(
            RoundingSessionRow.status.notin_(["COMPLETED", "ERROR"])
        )
        if robot_id is not None:
            query = query.filter(RoundingSessionRow.robot_id == robot_id)
        rows = query.order_by(RoundingSessionRow.started_at).all()
        return [_as_dict(r, ROUNDING_SESSION_FIELDS) for r in rows]
    finally:
        session.close()


def insert_patient_interaction(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(PatientInteractionRow(**row))
        session.commit()
    finally:
        session.close()


def list_patient_interactions(rounding_session_id: str) -> list:
    init_db()
    session = get_session()
    try:
        rows = (
            session.query(PatientInteractionRow)
            .filter_by(rounding_session_id=rounding_session_id)
            .order_by(PatientInteractionRow.id)
            .all()
        )
        return [_as_dict(r, PATIENT_INTERACTION_FIELDS) for r in rows]
    finally:
        session.close()


def insert_nurse_escalation(row: dict) -> None:
    init_db()
    session = get_session()
    try:
        session.add(NurseEscalationRow(**row))
        session.commit()
    finally:
        session.close()


def get_nurse_escalation(escalation_id: str) -> dict | None:
    init_db()
    session = get_session()
    try:
        row = session.get(NurseEscalationRow, escalation_id)
        return _as_dict(row, NURSE_ESCALATION_FIELDS) if row else None
    finally:
        session.close()


def list_nurse_escalations(status: str | None = None) -> list:
    """GET /escalations backing query. Newest-first is not assumed here --
    PR24's route layer / nurse dashboard sorts PENDING to the top; this
    just returns every row (optionally filtered by status) ordered by
    creation."""
    init_db()
    session = get_session()
    try:
        query = session.query(NurseEscalationRow)
        if status is not None:
            query = query.filter(NurseEscalationRow.status == status)
        rows = query.order_by(NurseEscalationRow.created_at).all()
        return [_as_dict(r, NURSE_ESCALATION_FIELDS) for r in rows]
    finally:
        session.close()


def acknowledge_nurse_escalation(
    escalation_id: str, acknowledged_by: str, acknowledged_at: "datetime"
) -> None:
    init_db()
    session = get_session()
    try:
        row = session.get(NurseEscalationRow, escalation_id)
        if row is not None:
            row.status = "ACKNOWLEDGED"
            row.acknowledged_by = acknowledged_by
            row.acknowledged_at = acknowledged_at
            session.commit()
    finally:
        session.close()


def delete_all_data() -> None:
    """Wipe every row from every table. Full reset, not a selective one --
    there's no column marking which rows are "seeded" vs real, so this is
    only appropriate against a local/demo database.
    """
    init_db()
    session = get_session()
    try:
        # PR22: new tables deleted first since care_requests /
        # rounding_sessions FKs point *to* them being gone already would
        # otherwise raise on backends that enforce FK constraints eagerly.
        session.query(NurseEscalationRow).delete()
        session.query(PatientInteractionRow).delete()
        session.query(TaskStateTransitionRow).delete()
        session.query(KitVerificationRow).delete()
        session.query(RobotEventRow).delete()
        session.query(RobotTaskRow).delete()
        session.query(CareRequestRow).delete()
        session.query(RoundingSessionRow).delete()
        session.commit()
    finally:
        session.close()
