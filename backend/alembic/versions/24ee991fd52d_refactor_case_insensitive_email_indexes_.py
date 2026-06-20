"""Refactor: Case-insensitive email indexes, Audit partitioning, and GC

Revision ID: 24ee991fd52d
Revises: 1c0f8cacc7f0
Create Date: 2026-06-20 03:40:42.006682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24ee991fd52d'
down_revision: Union[str, Sequence[str], None] = '1c0f8cacc7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Email Case Insensitivity Indexes
    op.execute("CREATE UNIQUE INDEX uq_user_tenant_email_lower ON users (tenant_id, LOWER(email));")
    op.execute("CREATE UNIQUE INDEX uq_invite_tenant_email_lower ON organization_invites (tenant_id, LOWER(email));")
    
    # 2. AuditLog Partitioning
    op.drop_table('audit_logs')
    op.execute("""
    CREATE TABLE audit_logs (
        id UUID NOT NULL,
        user_id UUID,
        tenant_id UUID NOT NULL,
        action VARCHAR(100) NOT NULL,
        ip_address VARCHAR(45),
        user_agent VARCHAR(500),
        device_fingerprint VARCHAR(64),
        metadata_json JSONB,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (id, timestamp),
        FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
    ) PARTITION BY RANGE (timestamp);
    """)
    op.create_index('idx_audit_tenant_time', 'audit_logs', ['tenant_id', 'timestamp'])
    op.create_index('idx_audit_user_time', 'audit_logs', ['user_id', 'timestamp'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])

    # Create initial partitions (e.g. for current and next month)
    op.execute("""
    CREATE TABLE audit_logs_y2026m06 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
    """)
    op.execute("""
    CREATE TABLE audit_logs_y2026m07 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX uq_user_tenant_email_lower;")
    op.execute("DROP INDEX uq_invite_tenant_email_lower;")
    
    op.drop_table('audit_logs')
    op.execute("""
    CREATE TABLE audit_logs (
        id UUID NOT NULL,
        user_id UUID,
        tenant_id UUID NOT NULL,
        action VARCHAR(100) NOT NULL,
        ip_address VARCHAR(45),
        user_agent VARCHAR(500),
        device_fingerprint VARCHAR(64),
        metadata_json JSON,
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
    );
    """)
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
