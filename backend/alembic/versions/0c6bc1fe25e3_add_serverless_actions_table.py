"""Add Serverless Actions table

Revision ID: 0c6bc1fe25e3
Revises: 1654d51f14ed
Create Date: 2026-06-20 08:41:42.532993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0c6bc1fe25e3'
down_revision: Union[str, Sequence[str], None] = '1654d51f14ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('actions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('trigger', sa.String(length=50), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_actions_tenant_id'), 'actions', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_actions_tenant_id'), table_name='actions')
    op.drop_table('actions')
