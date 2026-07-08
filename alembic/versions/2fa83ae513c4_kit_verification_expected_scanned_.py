"""kit verification expected/scanned detail (PR9)

Revision ID: 2fa83ae513c4
Revises: 715f1e4a7e2e
Create Date: 2026-07-09 03:18:08.440985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fa83ae513c4'
down_revision: Union[str, Sequence[str], None] = '715f1e4a7e2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kit_verifications', sa.Column('expected_patient_id', sa.String(), nullable=True))
    op.add_column('kit_verifications', sa.Column('scanned_patient_id', sa.String(), nullable=True))
    op.add_column('kit_verifications', sa.Column('expected_kit_id', sa.String(), nullable=True))
    op.add_column('kit_verifications', sa.Column('scanned_kit_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_kit_verifications_task_id'), 'kit_verifications', ['task_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kit_verifications_task_id'), table_name='kit_verifications')
    op.drop_column('kit_verifications', 'scanned_kit_id')
    op.drop_column('kit_verifications', 'expected_kit_id')
    op.drop_column('kit_verifications', 'scanned_patient_id')
    op.drop_column('kit_verifications', 'expected_patient_id')
