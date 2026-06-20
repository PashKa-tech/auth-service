import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

if TYPE_CHECKING:
    from src.models.tenant import Tenant
    from src.models.user import User

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(100)) # e.g. "login_success", "refresh_reuse_attack"
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    device_fingerprint: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict | None] = mapped_column(JSON) # Maps to JSONB in PG, JSON text in SQLite
    # Note: timestamp is part of the primary key to support PostgreSQL partitioning
    timestamp: Mapped[datetime] = mapped_column(DateTime, primary_key=True, server_default=func.now(), index=True)

    # Composite index for filtering logs by tenant and ordering by time
    __table_args__ = (
        Index("idx_audit_tenant_time", "tenant_id", "timestamp"),
        Index("idx_audit_user_time", "user_id", "timestamp"),
        {"postgresql_partition_by": "RANGE (timestamp)"},
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="audit_logs")
    user: Mapped["User | None"] = relationship(back_populates="audit_logs")
