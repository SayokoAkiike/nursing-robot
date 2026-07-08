"""task state transitions (PR8)

Revision ID: 715f1e4a7e2e
Revises: 05456d4b133d
Create Date: 2026-07-09 02:58:48.696572

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '715f1e4a7e2e'
down_revision: Union[str, Sequence[str], None] = '05456d4b133d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('task_state_transitions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.String(), nullable=False),
    sa.Column('request_id', sa.String(), nullable=False),
    sa.Column('from_state', sa.String(), nullable=True),
    sa.Column('to_state', sa.String(), nullable=False),
    sa.Column('trigger_type', sa.String(), nullable=False),
    sa.Column('triggered_by', sa.String(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('occurred_at', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_state_transitions_request_id'), 'task_state_transitions', ['request_id'], unique=False)
    op.create_index(op.f('ix_task_state_transitions_task_id'), 'task_state_transitions', ['task_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_task_state_transitions_task_id'), table_name='task_state_transitions')
    op.drop_index(op.f('ix_task_state_transitions_request_id'), table_name='task_state_transitions')
    op.drop_table('task_state_transitions')
