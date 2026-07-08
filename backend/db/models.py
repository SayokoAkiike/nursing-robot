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
(TERMINAL_TASK_STATES = {IDLE, COMPLETED}) at a time. This is the same rule
the old JSON singleton enforced implicitly (only one shared_state.json slot
existed); it is now scoped to `robot_id` instead of being a hardcoded
global, so introducing a second robot_id would allow two genuinely
concurrent tasks with no further schema changes.

Column types remain generic (String/Integer/Text) for SQLite/PostgreSQL
portability -- see the note in the PR2 version of this file.
"""
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CareRequestRow(Base):
    __tablename__ = "care_requests"

    id = Column(String, primary_key=True)
    patient_id = Column(String, nullable=True)
    request_type = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)


class RobotTaskRow(Base):
    __tablename__ = "robot_tasks"

    id = Column(String, primary_key=True)
    request_id = Column(String, nullable=False)
    robot_id = Column(String, nullable=False)
    state = Column(String, nullable=False, default="REQUEST_RECEIVED")
    kit_id = Column(String, nullable=True)
    assigned_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)


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
    task_id = Column(String, nullable=False, index=True)
    patient_id = Column(String, nullable=True)
    kit_id = Column(String, nullable=True)
    expected_patient_id = Column(String, nullable=True)
    scanned_patient_id = Column(String, nullable=True)
    expected_kit_id = Column(String, nullable=True)
    scanned_kit_id = Column(String, nullable=True)
    result = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(String, nullable=True)


class RobotEventRow(Base):
    __tablename__ = "robot_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=True)
    task_id = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
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
    task_id = Column(String, nullable=False, index=True)
    request_id = Column(String, nullable=False, index=True)
    from_state = Column(String, nullable=True)
    to_state = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False)
    triggered_by = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    occurred_at = Column(String, nullable=False)
