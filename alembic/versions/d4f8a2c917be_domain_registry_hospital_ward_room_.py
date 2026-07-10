"""domain registry: hospitals/wards/rooms/beds/patients/nurses/robots

Revision ID: d4f8a2c917be
Revises: 9c1f2b6a7d3e
Create Date: 2026-07-10 13:00:00.000000

Hand-written (not autogenerate), same reason as every other migration in
this repo: an intentional, readable upgrade/downgrade pair rather than
whatever alembic's autogenerate would produce.

Purely additive: seven new tables (backend/db/models.py's Hospital/Ward/
Room/Bed/Patient/Nurse/Robot), none of which is referenced by FK from any
existing table -- see backend/services/domain_service.py's module docstring
for why the existing patient_id/robot_id/room string columns elsewhere are
deliberately left as-is rather than migrated to real FKs in this same
change. Created in parent-to-child order (hospitals -> wards -> rooms ->
beds, with patients/nurses/robots depending on beds/wards/hospitals) so
each table's FK target already exists when it's created; downgrade drops
them in the reverse (child-to-parent) order for the same reason.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f8a2c917be'
down_revision: Union[str, Sequence[str], None] = '9c1f2b6a7d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'hospitals',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'wards',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('hospital_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_wards_hospital_id', 'wards', ['hospital_id'])
    op.create_table(
        'rooms',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('ward_id', sa.String(), nullable=False),
        sa.Column('number', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['ward_id'], ['wards.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rooms_ward_id', 'rooms', ['ward_id'])
    op.create_table(
        'beds',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('room_id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_beds_room_id', 'beds', ['room_id'])
    op.create_table(
        'patients',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('bed_id', sa.String(), nullable=True),
        sa.Column('allowed_kits', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['bed_id'], ['beds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_patients_bed_id', 'patients', ['bed_id'])
    op.create_table(
        'nurses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('ward_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['ward_id'], ['wards.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_nurses_ward_id', 'nurses', ['ward_id'])
    op.create_table(
        'robots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('hospital_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['hospital_id'], ['hospitals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_robots_hospital_id', 'robots', ['hospital_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_robots_hospital_id', table_name='robots')
    op.drop_table('robots')
    op.drop_index('ix_nurses_ward_id', table_name='nurses')
    op.drop_table('nurses')
    op.drop_index('ix_patients_bed_id', table_name='patients')
    op.drop_table('patients')
    op.drop_index('ix_beds_room_id', table_name='beds')
    op.drop_table('beds')
    op.drop_index('ix_rooms_ward_id', table_name='rooms')
    op.drop_table('rooms')
    op.drop_index('ix_wards_hospital_id', table_name='wards')
    op.drop_table('wards')
    op.drop_table('hospitals')
