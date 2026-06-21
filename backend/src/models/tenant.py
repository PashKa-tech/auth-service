import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, func, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.audit import AuditLog

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(2048))
    primary_color: Mapped[str] = mapped_column(String(7), default="#000000")
    font_family: Mapped[str] = mapped_column(String(100), default="Inter, sans-serif")
    pre_login_webhook_url: Mapped[str | None] = mapped_column(String(2048))
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=1000)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    api_keys: Mapped[list["TenantApiKey"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    invites: Mapped[list["OrganizationInvite"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255)) # e.g. "Production App Key"
    key_prefix: Mapped[str] = mapped_column(String(16)) # To identify the key (e.g. sk_prod_1234)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True) # SHA-256 hashed full key
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="api_keys")

class OrganizationInvite(Base):
    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    __table_args__ = (
        Index("uq_invite_tenant_email_lower", "tenant_id", text("lower(email)"), unique=True),
        CheckConstraint("role IN ('user', 'admin', 'manager')", name="chk_invite_role"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="invites")
