"""SQLAlchemy ORM models.
 
PR2 scope only: `care_requests` and `robot_events` (see backend/db/repositories.py
and the project roadmap). `robot_tasks` / `kit_verifications` -- and genuine
support for more than one concurrent task -- land in PR3 ("Task resource
model"). Until then `care_requests` is still, in effect, a single-row table:
`backend/db/repositories.py` clears it before inserting a new row, mirroring
the JSON file's whole-file overwrite semantics from before this PR.
 
Column types are kept deliberately generic (String/Integer/Text, no
Postgres-only types like JSONB/ARRAY) so the exact same models work against
both SQLite (used by the test suite and by default when DATABASE_URL is
unset) and PostgreSQL (via `docker-compose up`, see docker-compose.yml).
"""
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import declarative_base
 
Base = declarative_base()
 
 
class CareRequestRow(Base):
    __tablename__ = "care_requests"
 
    request_id = Column(String, primary_key=True)
    request_type = Column(String, nullable=True)
    request_label = Column(String, nullable=True)
    kit = Column(String, nullable=True)
    risk = Column(String, nullable=True)
    patient_id = Column(String, nullable=True)
    robot_state = Column(String, nullable=False, default="IDLE")
    timestamp = Column(String, nullable=True)
 
 
class RobotEventRow(Base):
    __tablename__ = "robot_events"
 
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    patient_id = Column(String, nullable=True)
    request = Column(String, nullable=True)
    kit = Column(String, nullable=True)
    previous_state = Column(String, nullable=True)
    next_state = Column(String, nullable=True)
    result = Column(String, nullable=True)
    message = Column(Text, nullable=True)
 
