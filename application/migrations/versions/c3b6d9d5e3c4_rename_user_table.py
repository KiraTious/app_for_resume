"""rename user table to users

Revision ID: c3b6d9d5e3c4
Revises: f1a04d9b8c3b
Create Date: 2025-12-20 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'c3b6d9d5e3c4'
down_revision = 'f1a04d9b8c3b'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('user', 'users')


def downgrade():
    op.rename_table('users', 'user')
