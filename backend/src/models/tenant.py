import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=1000)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("TenantApiKey", back_populates="tenant", cascade="all, delete-orphan")

class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False) # e.g. "Production App Key"
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False) # To identify the key (e.g. sk_prod_1234)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True) # SHA-256 hashed full key
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="api_keys")
