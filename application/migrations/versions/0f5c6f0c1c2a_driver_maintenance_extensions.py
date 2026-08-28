"""driver maintenance extensions

Revision ID: 0f5c6f0c1c2a
Revises: c3b6d9d5e3c4
Create Date: 2025-12-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0f5c6f0c1c2a'
down_revision = 'c3b6d9d5e3c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('maintenance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operation_type', sa.String(length=20), nullable=False, server_default='service'))
        batch_op.add_column(sa.Column('event_date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')))
        batch_op.add_column(sa.Column('mileage_km', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fuel_volume_l', sa.Float(), nullable=True))
        batch_op.alter_column('type_of_work', existing_type=sa.String(length=100), nullable=True)

    # remove server defaults now that existing rows are populated
    with op.batch_alter_table('maintenance', schema=None) as batch_op:
        batch_op.alter_column('operation_type', server_default=None)
        batch_op.alter_column('event_date', server_default=None)


def downgrade():
    with op.batch_alter_table('maintenance', schema=None) as batch_op:
        batch_op.alter_column('type_of_work', existing_type=sa.String(length=100), nullable=False)
        batch_op.drop_column('fuel_volume_l')
        batch_op.drop_column('mileage_km')
        batch_op.drop_column('event_date')
        batch_op.drop_column('operation_type')
