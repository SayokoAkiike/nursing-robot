"""nurse_escalations: nullable rounding_session_id + auto-escalation fields

Revision ID: 9c1f2b6a7d3e
Revises: 71a902b00d13
Create Date: 2026-07-10 12:00:00.000000

Hand-written (not autogenerate), same reason as PR15/PR22: SQLite cannot
ALTER a column's nullability or add a column with a server default outside
of batch mode, so this whole migration runs inside a single
`op.batch_alter_table(...)` block.

Two independent changes bundled into one revision because they land in the
same table and the same feature (see `backend/db/models.py`'s
`NurseEscalationRow` docstring for the full rationale):

  - `rounding_session_id` NOT NULL -> nullable, so a delivery-flow ERROR
    (raised by `workflow_service._raise_error_escalation()`, which has no
    rounding session to attach to) can be inserted at all.
  - `escalated_count` (Integer, NOT NULL, default 0), `last_escalated_at`
    (DateTime, nullable), `source` (String, nullable) support
    `escalation_service.check_and_escalate_overdue()`'s priority-bump
    trail and let callers tell a rounding-originated escalation apart
    from a delivery-error one.

`escalated_count` needs `server_default='0'` (not just the ORM-side
`default=0` in models.py) because existing rows in a real deployment's
table already exist at migration time and must satisfy the new NOT NULL
constraint immediately -- the ORM-side default only applies to rows
inserted after the model change is loaded, not to rows already on disk.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c1f2b6a7d3e'
down_revision: Union[str, Sequence[str], None] = '71a902b00d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('nurse_escalations', schema=None) as batch_op:
        batch_op.alter_column(
            'rounding_session_id',
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                'escalated_count',
                sa.Integer(),
                nullable=False,
                server_default='0',
            )
        )
        batch_op.add_column(sa.Column('last_escalated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('source', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    NOTE: if any row was inserted with `rounding_session_id IS NULL` (i.e.
    any delivery-flow error escalation exists), re-adding the NOT NULL
    constraint below will fail -- that data loss/conflict has to be
    resolved by hand (delete or backfill those rows) before downgrading
    past this revision. This is a deliberate one-way door, not an
    oversight: the whole point of this revision is that such rows are now
    valid.
    """
    with op.batch_alter_table('nurse_escalations', schema=None) as batch_op:
        batch_op.drop_column('source')
        batch_op.drop_column('last_escalated_at')
        batch_op.drop_column('escalated_count')
        batch_op.alter_column(
            'rounding_session_id',
            existing_type=sa.String(),
            nullable=False,
        )
