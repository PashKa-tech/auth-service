"""Enable RLS for sessions and tokens

Revision ID: 4b5b075f75f7
Revises: 5c9addc0a35e
Create Date: 2026-06-21 20:05:50.686548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b5b075f75f7'
down_revision: Union[str, Sequence[str], None] = '5c9addc0a35e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create a STABLE function for getting current tenant to allow index usage in RLS
    op.execute('''
        CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS uuid AS $$
            SELECT NULLIF(current_setting('app.current_tenant', true), '')::uuid;
        $$ LANGUAGE SQL STABLE;
    ''')

    # 2. Tables that already have RLS
    tables_with_tenant = [
        "users", "audit_logs", "roles", "tenant_api_keys",
        "organization_invites", "actions", "m2m_apps", "saml_configs",
        "two_factor_backup_codes", "webauthn_credentials", "webhooks"
    ]

    # Update existing policies to use the new STABLE function
    for table in tables_with_tenant:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_policy ON {table};")
        op.execute(f'''
            CREATE POLICY {table}_tenant_isolation_policy ON {table}
            USING (
                current_setting('app.current_tenant', true) IS NULL
                OR current_setting('app.current_tenant', true) = ''
                OR tenant_id = current_tenant_id()
            );
        ''')

    # 3. New tables to enable RLS on
    new_tables = ["sessions", "refresh_tokens", "verification_tokens"]
    for table in new_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f'''
            CREATE POLICY {table}_tenant_isolation_policy ON {table}
            USING (
                current_setting('app.current_tenant', true) IS NULL
                OR current_setting('app.current_tenant', true) = ''
                OR tenant_id = current_tenant_id()
            );
        ''')


def downgrade() -> None:
    new_tables = ["sessions", "refresh_tokens", "verification_tokens"]
    for table in new_tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    tables_with_tenant = [
        "users", "audit_logs", "roles", "tenant_api_keys",
        "organization_invites", "actions", "m2m_apps", "saml_configs",
        "two_factor_backup_codes", "webauthn_credentials", "webhooks"
    ]
    for table in tables_with_tenant:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_policy ON {table};")
        op.execute(f'''
            CREATE POLICY {table}_tenant_isolation_policy ON {table}
            USING (
                current_setting('app.current_tenant', true) IS NULL
                OR current_setting('app.current_tenant', true) = ''
                OR tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            );
        ''')
    
    op.execute("DROP FUNCTION IF EXISTS current_tenant_id();")
