"""auth roles and password len

Revision ID: f1a04d9b8c3b
Revises: b73bdc69f02e
Create Date: 2025-12-15 07:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a04d9b8c3b'
down_revision = 'b73bdc69f02e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'password',
            existing_type=sa.String(length=100),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'role',
            existing_type=sa.String(length=50),
            server_default='driver',
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column(
            'role',
            existing_type=sa.String(length=50),
            server_default=None,
            existing_nullable=False,
        )
        batch_op.alter_column(
            'password',
            existing_type=sa.String(length=255),
            type_=sa.String(length=100),
            existing_nullable=False,
        )
