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
    __tablename__ = "kit_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False)
    patient_id = Column(String, nullable=True)
    kit_id = Column(String, nullable=True)
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

