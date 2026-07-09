"""PR15: DateTime timestamps, FKs, active-task-per-robot unique index

Revision ID: 4a6da14949bf
Revises: 2fa83ae513c4
Create Date: 2026-07-09 13:06:00.177277

Hand-edited after autogenerate: SQLite does not support ALTER TABLE ...
ALTER COLUMN or adding a foreign key to an existing table in place, so
every column-type change / new FK below is wrapped in
op.batch_alter_table(...), which recreates each table under the hood
(copy-data-drop-rename) instead of altering it in place. This works
identically against PostgreSQL (batch mode there is a no-op passthrough
to plain ALTER TABLE). Index creation/drop is untouched -- SQLite supports
CREATE INDEX (including partial WHERE indexes) natively, no batch mode
needed for those.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4a6da14949bf'
down_revision: Union[str, Sequence[str], None] = '2fa83ae513c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('care_requests', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=True)
        batch_op.alter_column('completed_at',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=True)

    with op.batch_alter_table('kit_verifications', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=True)
        batch_op.create_foreign_key(
            'fk_kit_verifications_task_id_robot_tasks',
            'robot_tasks', ['task_id'], ['id'])

    with op.batch_alter_table('robot_events', schema=None) as batch_op:
        batch_op.alter_column('timestamp',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=False)
        batch_op.create_foreign_key(
            'fk_robot_events_request_id_care_requests',
            'care_requests', ['request_id'], ['id'])
        batch_op.create_foreign_key(
            'fk_robot_events_task_id_robot_tasks',
            'robot_tasks', ['task_id'], ['id'])

    with op.batch_alter_table('robot_tasks', schema=None) as batch_op:
        batch_op.alter_column('assigned_at',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=True)
        batch_op.alter_column('updated_at',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=True)
        batch_op.create_foreign_key(
            'fk_robot_tasks_request_id_care_requests',
            'care_requests', ['request_id'], ['id'])

    op.create_index('ix_robot_tasks_request_id', 'robot_tasks', ['request_id'], unique=False)
    op.create_index('ux_robot_tasks_active_robot', 'robot_tasks', ['robot_id'], unique=True,
                     sqlite_where=sa.text("state NOT IN ('IDLE', 'COMPLETED', 'ERROR')"),
                     postgresql_where=sa.text("state NOT IN ('IDLE', 'COMPLETED', 'ERROR')"))

    with op.batch_alter_table('task_state_transitions', schema=None) as batch_op:
        batch_op.alter_column('occurred_at',
                   existing_type=sa.VARCHAR(),
                   type_=sa.DateTime(),
                   existing_nullable=False)
        batch_op.create_foreign_key(
            'fk_task_state_transitions_task_id_robot_tasks',
            'robot_tasks', ['task_id'], ['id'])
        batch_op.create_foreign_key(
            'fk_task_state_transitions_request_id_care_requests',
            'care_requests', ['request_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('task_state_transitions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_task_state_transitions_request_id_care_requests', type_='foreignkey')
        batch_op.drop_constraint('fk_task_state_transitions_task_id_robot_tasks', type_='foreignkey')
        batch_op.alter_column('occurred_at',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=False)

    op.drop_index('ux_robot_tasks_active_robot', table_name='robot_tasks',
                   sqlite_where=sa.text("state NOT IN ('IDLE', 'COMPLETED', 'ERROR')"),
                   postgresql_where=sa.text("state NOT IN ('IDLE', 'COMPLETED', 'ERROR')"))
    op.drop_index('ix_robot_tasks_request_id', table_name='robot_tasks')

    with op.batch_alter_table('robot_tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_robot_tasks_request_id_care_requests', type_='foreignkey')
        batch_op.alter_column('updated_at',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=True)
        batch_op.alter_column('assigned_at',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=True)

    with op.batch_alter_table('robot_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_robot_events_task_id_robot_tasks', type_='foreignkey')
        batch_op.drop_constraint('fk_robot_events_request_id_care_requests', type_='foreignkey')
        batch_op.alter_column('timestamp',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=False)

    with op.batch_alter_table('kit_verifications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_kit_verifications_task_id_robot_tasks', type_='foreignkey')
        batch_op.alter_column('created_at',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=True)

    with op.batch_alter_table('care_requests', schema=None) as batch_op:
        batch_op.alter_column('completed_at',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=True)
        batch_op.alter_column('created_at',
                   existing_type=sa.DateTime(),
                   type_=sa.VARCHAR(),
                   existing_nullable=True)
