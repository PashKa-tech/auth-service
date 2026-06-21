"""create audit logs partition

Revision ID: c4b3d5e6f7a8
Revises: b3a2c4d5e6f7
Create Date: 2026-06-21 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4b3d5e6f7a8'
down_revision: Union[str, None] = 'b3a2c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create partitions for 2026, 2027
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs_y2026 PARTITION OF audit_logs
        FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs_y2027 PARTITION OF audit_logs
        FOR VALUES FROM ('2027-01-01 00:00:00+00') TO ('2028-01-01 00:00:00+00');
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs_y2026;")
    op.execute("DROP TABLE IF EXISTS audit_logs_y2027;")
