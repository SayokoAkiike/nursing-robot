"""SQLAlchemy ORM models.

PR2 introduced `care_requests` / `robot_events` as a still-singleton design
(one active row at a time, mirroring the old JSON file). PR3 ("Task
resource model") splits the workflow into three real, independently
addressable tables:

  - `care_requests`: the patient's request itself (what/who/when), no
    robot-workflow state.
  - `robot_tasks`: the actual robot execution of a request (one row per
    task, `state` holds the finite-state-machine value from
    `services/robot_service.py`). A request gets a task the moment it's
    assigned to a robot.
  - `kit_verifications`: one row per QR verification *attempt* (OK or NG),
    independent of `robot_events` -- an audit trail that can be queried on
    its own (e.g. by the evaluation work in a later PR) without filtering
    the generic event log by event_type.

Concurrency rule (see `backend/services/workflow_service.py`): at most one
`robot_tasks` row per `robot_id` may be in a non-terminal state
(TERMINAL_TASK_STATES = {IDLE, COMPLETED}) at a time. Until PR15 this rule
was enforced only in application code (`workflow_service.create_request`'s
check-then-act against `repositories.get_active_task_for_robot`), which is
a real TOCTOU race under concurrent requests. PR15 adds a partial unique
index (`ux_robot_tasks_active_robot`) so the database itself refuses a
second non-terminal row for the same robot_id -- the application check
stays as a fast, friendly pre-check, but the index is what actually
guarantees the invariant now. Must stay in sync with
`repositories.NON_BLOCKING_TASK_STATES` (currently {"IDLE", "COMPLETED",
"ERROR"}) -- the WHERE clause below is written in raw SQL since SQLAlchemy
partial-index where-clauses need to be evaluable at table-definition time.

PR15 also switches every timestamp column from String to DateTime. Two
concrete problems this fixes: (1) `robot_events.timestamp` was written via
`datetime.now().strftime("%Y-%m-%d %H:%M:%S")` while every other timestamp
column used `datetime.now().isoformat()` -- two incompatible string
formats coexisted in the same database. (2) `analytics_service.py` and
`repositories.shift_timestamps_for_request` both had to manually
`datetime.fromisoformat()` / `datetime.strptime()` values back out of the
DB on every read. SQLAlchemy's DateTime type works the same way against
both SQLite and PostgreSQL, so this doesn't cost the SQLite/PostgreSQL
portability the previous String columns were chosen for.

FK constraints are new in PR15 too (previously request_id/task_id were
plain String columns with no DB-level referential integrity).

PR22 ("domain/rounding-models") adds three new, purely additive tables for
the rounding/check-in workflow proposed alongside the existing
request-driven delivery workflow:

  - `rounding_sessions`: one row per robot rounding pass through a room.
  - `patient_interactions`: one row per prompt/response exchange within a
    rounding session (voice/tablet/simulated/manual input_mode).
  - `nurse_escalations`: the queue of things a nurse needs to see/ack,
    raised either from a rounding session or (in principle) manually.

`care_requests` also gains two new nullable columns, `source` and
`rounding_session_id`, so a request can record whether it came from the
patient tablet, a robot's rounding conversation, a manual nurse entry, or
a demo seed script -- and, if it came from rounding, which session raised
it. Both are nullable with no new NOT NULL/default constraints on the
existing table, so this migration never touches the shape of existing
rows; the `ROUNDING_ALLOWED_TRANSITIONS` state machine and
`rounding_service` module built on top of these tables are introduced in
PR23, kept deliberately separate from `ALLOWED_TRANSITIONS` /
`robot_tasks` (see `backend/services/robot_service.py` for why).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Must match repositories.NON_BLOCKING_TASK_STATES.
_ACTIVE_TASK_WHERE = text("state NOT IN ('IDLE', 'COMPLETED', 'ERROR')")


class CareRequestRow(Base):
    __tablename__ = "care_requests"

    id = Column(String, primary_key=True)
    patient_id = Column(String, nullable=True)
    request_type = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    # PR22: origin of the request. Nullable (and left unbackfilled for
    # existing rows) rather than NOT NULL + default, so this migration
    # cannot fail against any pre-existing data -- callers that care about
    # provenance (workflow_service.create_request, the future
    # rounding_service) always pass it explicitly going forward.
    # Expected values: "patient_tablet" | "robot_rounding" | "nurse_manual"
    # | "demo_seed".
    source = Column(String, nullable=True)
    # PR22: set only when source == "robot_rounding" -- the rounding
    # session whose need-classification produced this request.
    rounding_session_id = Column(
        String, ForeignKey("rounding_sessions.id"), nullable=True
    )


class RobotTaskRow(Base):
    __tablename__ = "robot_tasks"
    __table_args__ = (
        Index("ix_robot_tasks_request_id", "request_id"),
        Index(
            "ux_robot_tasks_active_robot",
            "robot_id",
            unique=True,
            sqlite_where=_ACTIVE_TASK_WHERE,
            postgresql_where=_ACTIVE_TASK_WHERE,
        ),
    )

    id = Column(String, primary_key=True)
    request_id = Column(String, ForeignKey("care_requests.id"), nullable=False)
    robot_id = Column(String, nullable=False)
    state = Column(String, nullable=False, default="REQUEST_RECEIVED")
    kit_id = Column(String, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class KitVerificationRow(Base):
    """One row per QR verification *attempt* (OK or NG).

    PR9: `patient_id` / `kit_id` are kept for backward compatibility and
    mean the *scanned* value (what the QR code actually said) -- they are
    plain aliases for `scanned_patient_id` / `scanned_kit_id` below, always
    written together. The new `expected_*` / `scanned_*` columns make the
    NG-cause auditable: with only the old columns, an NG row didn't say
    what was *supposed* to be scanned, only what *was* scanned, so a
    patient-mismatch and a kit-mismatch looked identical without re-reading
    the free-text `message`.
    """

    __tablename__ = "kit_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("robot_tasks.id"), nullable=False, index=True)
    patient_id = Column(String, nullable=True)
    kit_id = Column(String, nullable=True)
    expected_patient_id = Column(String, nullable=True)
    scanned_patient_id = Column(String, nullable=True)
    expected_kit_id = Column(String, nullable=True)
    scanned_kit_id = Column(String, nullable=True)
    result = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)


class RobotEventRow(Base):
    __tablename__ = "robot_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, ForeignKey("care_requests.id"), nullable=True)
    task_id = Column(String, ForeignKey("robot_tasks.id"), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String, nullable=False)
    patient_id = Column(String, nullable=True)
    request = Column(String, nullable=True)
    kit = Column(String, nullable=True)
    previous_state = Column(String, nullable=True)
    next_state = Column(String, nullable=True)
    result = Column(String, nullable=True)
    message = Column(Text, nullable=True)


class TaskStateTransitionRow(Base):
    """PR8: structured, queryable history of every robot_tasks.state change.

    `robot_events` (above) is the human-readable log used by the nurse
    dashboard's log view. This table is a separate, analysis-oriented
    record of the same underlying fact (a state changed) -- one row per
    transition, with a machine-friendly `trigger_type`/`triggered_by`
    instead of a free-text message, so it can be queried/aggregated
    directly (see PR11's /analytics/state-durations) without parsing log
    text.
    """

    __tablename__ = "task_state_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("robot_tasks.id"), nullable=False, index=True)
    request_id = Column(String, ForeignKey("care_requests.id"), nullable=False, index=True)
    from_state = Column(String, nullable=True)
    to_state = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False)
    triggered_by = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False)


# ---------------------------------------------------------------------------
# PR22: rounding / check-in workflow tables (additive; see module docstring)
# ---------------------------------------------------------------------------


class RoundingSessionRow(Base):
    """One row per robot rounding pass through a room.

    `status` holds the rounding-side finite-state-machine value from
    `ROUNDING_ALLOWED_TRANSITIONS` (backend/services/robot_service.py,
    PR23) -- deliberately a separate value space from `robot_tasks.state`,
    since a rounding session and a delivery task are different things that
    can coexist (a rounding session's need-classification can spawn a
    `care_requests` row, which in turn gets its own `robot_tasks` row).
    """

    __tablename__ = "rounding_sessions"
    __table_args__ = (Index("ix_rounding_sessions_robot_id", "robot_id"),)

    id = Column(String, primary_key=True)
    robot_id = Column(String, nullable=False)
    room = Column(String, nullable=False)
    patient_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ROUNDING")
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    interaction_summary = Column(Text, nullable=True)
    detected_need = Column(String, nullable=True)
    escalation_level = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class PatientInteractionRow(Base):
    """One row per prompt/response exchange within a rounding session.

    `input_mode` is expected to be one of "voice" | "tablet" | "simulated"
    | "manual". Real speech recognition is out of scope for PR22-PR26 --
    "simulated" and "manual" are the only modes actually produced by the
    scripts/UI added in this phase; "voice" and "tablet" are reserved so
    the schema doesn't need another migration once real input lands.
    """

    __tablename__ = "patient_interactions"
    __table_args__ = (
        Index("ix_patient_interactions_rounding_session_id", "rounding_session_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    rounding_session_id = Column(
        String, ForeignKey("rounding_sessions.id"), nullable=False
    )
    patient_id = Column(String, nullable=True)
    room = Column(String, nullable=True)
    prompt = Column(Text, nullable=True)
    patient_response = Column(Text, nullable=True)
    input_mode = Column(String, nullable=False, default="simulated")
    detected_need = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)


class NurseEscalationRow(Base):
    """The queue of things a nurse needs to see and acknowledge.

    `request_id` is nullable: an escalation can exist purely as a
    notification (route == NURSE_NOTIFICATION, no delivery involved) with
    no corresponding `care_requests` row, or it can be raised alongside one
    (route == DELIVERY_REQUIRED plus a same-visit notification).
    """

    __tablename__ = "nurse_escalations"
    __table_args__ = (
        Index("ix_nurse_escalations_rounding_session_id", "rounding_session_id"),
        Index("ix_nurse_escalations_status", "status"),
    )

    id = Column(String, primary_key=True)
    rounding_session_id = Column(
        String, ForeignKey("rounding_sessions.id"), nullable=False
    )
    request_id = Column(String, ForeignKey("care_requests.id"), nullable=True)
    patient_id = Column(String, nullable=True)
    room = Column(String, nullable=True)
    summary = Column(Text, nullable=False)
    priority = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)
