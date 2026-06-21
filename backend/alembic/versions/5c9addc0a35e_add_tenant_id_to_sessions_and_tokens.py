"""Add tenant_id to sessions and tokens

Revision ID: 5c9addc0a35e
Revises: c4b3d5e6f7a8
Create Date: 2026-06-21 20:05:29.844604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c9addc0a35e'
down_revision: Union[str, Sequence[str], None] = 'c4b3d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add tenant_id columns (nullable initially to allow adding foreign key constraints before backfilling if needed, though they should be non-nullable eventually)
    op.add_column('sessions', sa.Column('tenant_id', sa.Uuid(), nullable=True))
    op.add_column('refresh_tokens', sa.Column('tenant_id', sa.Uuid(), nullable=True))
    op.add_column('verification_tokens', sa.Column('tenant_id', sa.Uuid(), nullable=True))

    # 2. Add foreign keys
    op.create_foreign_key(None, 'sessions', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'refresh_tokens', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'verification_tokens', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # 3. Add indices
    op.create_index(op.f('ix_sessions_tenant_id'), 'sessions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_tenant_id'), 'refresh_tokens', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_verification_tokens_tenant_id'), 'verification_tokens', ['tenant_id'], unique=False)


def downgrade() -> None:
    # 1. Drop indices
    op.drop_index(op.f('ix_verification_tokens_tenant_id'), table_name='verification_tokens')
    op.drop_index(op.f('ix_refresh_tokens_tenant_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_sessions_tenant_id'), table_name='sessions')

    # 2. Drop foreign keys
    op.drop_constraint(None, 'verification_tokens', type_='foreignkey')
    op.drop_constraint(None, 'refresh_tokens', type_='foreignkey')
    op.drop_constraint(None, 'sessions', type_='foreignkey')

    # 3. Drop columns
    op.drop_column('verification_tokens', 'tenant_id')
    op.drop_column('refresh_tokens', 'tenant_id')
    op.drop_column('sessions', 'tenant_id')
