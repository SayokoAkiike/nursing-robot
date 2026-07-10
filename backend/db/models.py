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

Escalation safety-net revision: `nurse_escalations.rounding_session_id`
switches from NOT NULL to nullable, and three columns are added
(`escalated_count`, `last_escalated_at`, `source`). This closes two gaps:
(1) a delivery-flow ERROR (QR mismatch, an attempted KIT_RELEASED without
nurse confirmation, an emergency stop) previously had no way to reach the
nurse_escalations queue at all, since every existing writer of that table
was rounding_service and always had a session to attach to --
`workflow_service._raise_error_escalation()` is the first writer that
doesn't; (2) a PENDING escalation could sit unacknowledged indefinitely
with no visible urgency change -- `escalation_service.
check_and_escalate_overdue()` now bumps priority one step after
`backend.core.config.ESCALATION_TIMEOUT_SECONDS` elapses, recording the
bump in these two new columns rather than silently mutating `priority`
with no trace.
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

    `rounding_session_id` was originally NOT NULL (every escalation came
    from a rounding session). It is now nullable: `workflow_service`'s
    delivery flow raises an escalation directly on a safety-relevant
    ERROR (QR mismatch, an attempted KIT_RELEASED without nurse
    confirmation, emergency stop) without ever having a rounding session
    to attach to -- see `workflow_service._raise_error_escalation()`.
    `source` (nullable, "rounding" | "delivery_error") is how callers/UI
    tell the two origins apart without a schema change every time a third
    origin shows up.

    `escalated_count` / `last_escalated_at` back
    `escalation_service.check_and_escalate_overdue()`: a PENDING
    escalation left unacknowledged past its priority's timeout
    (`backend.core.config.ESCALATION_TIMEOUT_SECONDS`) has its priority
    bumped one step and these two fields updated, so the nurse dashboard
    can show "this was auto-escalated" instead of silently changing
    priority with no trace.
    """

    __tablename__ = "nurse_escalations"
    __table_args__ = (
        Index("ix_nurse_escalations_rounding_session_id", "rounding_session_id"),
        Index("ix_nurse_escalations_status", "status"),
    )

    id = Column(String, primary_key=True)
    rounding_session_id = Column(
        String, ForeignKey("rounding_sessions.id"), nullable=True
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
    escalated_count = Column(Integer, nullable=False, default=0)
    last_escalated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True)


# ---------------------------------------------------------------------------
# Domain registry tables (item 4): Hospital -> Ward -> Room -> Bed, plus
# Patient/Nurse/Robot. Purely additive, same spirit as PR22's rounding
# tables -- nothing above (care_requests/robot_tasks/rounding_sessions/
# nurse_escalations, all of which use plain patient_id/robot_id/room
# *string* columns) is changed to a real FK against these new tables in this
# same change. See backend/services/domain_service.py's module docstring for
# why that wiring is deliberately deferred to its own follow-up rather than
# bundled here.
# ---------------------------------------------------------------------------


class HospitalRow(Base):
    __tablename__ = "hospitals"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class WardRow(Base):
    __tablename__ = "wards"
    __table_args__ = (Index("ix_wards_hospital_id", "hospital_id"),)

    id = Column(String, primary_key=True)
    hospital_id = Column(String, ForeignKey("hospitals.id"), nullable=False)
    name = Column(String, nullable=False)


class RoomRow(Base):
    __tablename__ = "rooms"
    __table_args__ = (Index("ix_rooms_ward_id", "ward_id"),)

    id = Column(String, primary_key=True)
    ward_id = Column(String, ForeignKey("wards.id"), nullable=False)
    number = Column(String, nullable=False)


class BedRow(Base):
    __tablename__ = "beds"
    __table_args__ = (Index("ix_beds_room_id", "room_id"),)

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    label = Column(String, nullable=False)


class PatientRow(Base):
    """Registry entry for a patient, keyed by the same string id already
    used throughout care_requests/robot_tasks/rounding_sessions/etc. (e.g.
    "PATIENT_A_ROOM_203"). Adds structured hospital/ward/room/bed placement
    and the allowed_kits safety list on top of what previously lived only in
    the `PATIENTS` dict in backend/core/config.py -- see
    backend/services/domain_service.py's `seed_default_domain_data()`,
    which mirrors that same dict into this table.

    `allowed_kits` is stored as a comma-separated string (e.g.
    "KIT_TOILETING_A,KIT_WATER,ALERT_NURSE_ONLY"), mirroring
    `PATIENTS[...]["allowed_kits"]`'s list shape without adding a
    dependency on a JSON column type -- see domain_service.py's
    `split_allowed_kits()`/`join_allowed_kits()`.
    """

    __tablename__ = "patients"
    __table_args__ = (Index("ix_patients_bed_id", "bed_id"),)

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    bed_id = Column(String, ForeignKey("beds.id"), nullable=True)
    allowed_kits = Column(Text, nullable=True)


class NurseRow(Base):
    __tablename__ = "nurses"
    __table_args__ = (Index("ix_nurses_ward_id", "ward_id"),)

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    ward_id = Column(String, ForeignKey("wards.id"), nullable=True)


class RobotRow(Base):
    __tablename__ = "robots"
    __table_args__ = (Index("ix_robots_hospital_id", "hospital_id"),)

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    hospital_id = Column(String, ForeignKey("hospitals.id"), nullable=True)
