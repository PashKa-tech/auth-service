"""Add composite indexes for sessions and users

Revision ID: b21b97c6ef52
Revises: 4b5b075f75f7
Create Date: 2026-06-21 23:24:22.484525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b21b97c6ef52'
down_revision: Union[str, Sequence[str], None] = '4b5b075f75f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('idx_sessions_user_created_at', 'sessions', ['user_id', sa.text('created_at DESC')])
    op.create_index('idx_users_tenant_created_at', 'users', ['tenant_id', 'created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_users_tenant_created_at', table_name='users')
    op.drop_index('idx_sessions_user_created_at', table_name='sessions')
