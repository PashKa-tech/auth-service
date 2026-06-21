"""enable rls

Revision ID: b3a2c4d5e6f7
Revises: f29a1b2c3d4e
Create Date: 2026-06-21 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3a2c4d5e6f7'
down_revision: Union[str, None] = 'f29a1b2c3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables_with_tenant = [
        "users", "audit_logs", "roles", "tenant_api_keys",
        "organization_invites", "actions", "m2m_apps", "saml_configs",
        "two_factor_backup_codes", "webauthn_credentials", "webhooks"
    ]
    
    for table in tables_with_tenant:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # If app.current_tenant is not set (NULL) or empty, allow all (safe migration path). 
        # Otherwise restrict to the specific tenant.
        op.execute(f'''
            CREATE POLICY {table}_tenant_isolation_policy ON {table}
            USING (
                current_setting('app.current_tenant', true) IS NULL
                OR current_setting('app.current_tenant', true) = ''
                OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            );
        ''')


def downgrade() -> None:
    tables_with_tenant = [
        "users", "audit_logs", "roles", "tenant_api_keys",
        "organization_invites", "actions", "m2m_apps", "saml_configs",
        "two_factor_backup_codes", "webauthn_credentials", "webhooks"
    ]
    
    for table in tables_with_tenant:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
