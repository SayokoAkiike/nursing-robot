"""task resource model: robot_tasks, kit_verifications

Revision ID: 05456d4b133d
Revises: fa116680c547
Create Date: 2026-07-08 21:56:20.116034

care_requests is redesigned (see backend/db/models.py's docstring: it goes
from a singleton "current state" row to a real per-request row, with the
robot-workflow state moved out to the new robot_tasks table). Autogenerate
produced an ALTER-based migration that adds a new `id` column without ever
making it the primary key -- SQLite/PostgreSQL don't let you promote a
plain column to a PK via ALTER in a single portable step, and there's no
production data to preserve yet, so this migration drops and recreates
care_requests instead of altering it column-by-column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05456d4b133d'
down_revision: Union[str, Sequence[str], None] = 'fa116680c547'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'robot_tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('robot_id', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('kit_id', sa.String(), nullable=True),
        sa.Column('assigned_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'kit_verifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('patient_id', sa.String(), nullable=True),
        sa.Column('kit_id', sa.String(), nullable=True),
        sa.Column('result', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('robot_events', sa.Column('task_id', sa.String(), nullable=True))

    # care_requests: drop and recreate with the new per-request schema (no
    # production data to migrate yet -- see module docstring above).
    op.drop_table('care_requests')
    op.create_table(
        'care_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('patient_id', sa.String(), nullable=True),
        sa.Column('request_type', sa.String(), nullable=True),
        sa.Column('priority', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('completed_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('care_requests')
    op.create_table(
        'care_requests',
        sa.Column('request_id', sa.String(), nullable=False),
        sa.Column('request_type', sa.String(), nullable=True),
        sa.Column('request_label', sa.String(), nullable=True),
        sa.Column('kit', sa.String(), nullable=True),
        sa.Column('risk', sa.String(), nullable=True),
        sa.Column('patient_id', sa.String(), nullable=True),
        sa.Column('robot_state', sa.String(), nullable=False),
        sa.Column('timestamp', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('request_id'),
    )
    op.drop_column('robot_events', 'task_id')
    op.drop_table('kit_verifications')
    op.drop_table('robot_tasks')

