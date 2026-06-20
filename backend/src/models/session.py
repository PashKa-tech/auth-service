import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True) # Max length for IPv6
    location: Mapped[str | None] = mapped_column(String(255), nullable=True) # e.g. "Berlin, Germany"
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    os_info: Mapped[str | None] = mapped_column(String(100), nullable=True) # e.g. "Windows 10"
    browser_info: Mapped[str | None] = mapped_column(String(100), nullable=True) # e.g. "Chrome 110"
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True) # e.g. "PC", "Mobile", "Tablet"
    device_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True) # SHA-256 hash
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Composite Index for checking active sessions of a user
    __table_args__ = (
        Index("idx_session_user_revoked", "user_id", "is_revoked"),
    )

    # Relationships
    user = relationship("User", back_populates="sessions")
    refresh_tokens = relationship("RefreshToken", back_populates="session", cascade="all, delete-orphan")
