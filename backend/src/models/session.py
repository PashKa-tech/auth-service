import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.token import RefreshToken

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45)) # Max length for IPv6
    location: Mapped[str | None] = mapped_column(String(255)) # e.g. "Berlin, Germany"
    user_agent: Mapped[str | None] = mapped_column(String(500))
    os_info: Mapped[str | None] = mapped_column(String(100)) # e.g. "Windows 10"
    browser_info: Mapped[str | None] = mapped_column(String(100)) # e.g. "Chrome 110"
    device_type: Mapped[str | None] = mapped_column(String(50)) # e.g. "PC", "Mobile", "Tablet"
    device_fingerprint: Mapped[str | None] = mapped_column(String(64)) # SHA-256 hash
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    # Composite Index for checking active sessions of a user
    __table_args__ = (
        Index("idx_session_user_revoked", "user_id", "is_revoked"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="session", cascade="all, delete-orphan")
