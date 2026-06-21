import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

if TYPE_CHECKING:
    from src.models.user import User

class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50)) # e.g. "google", "github"
    provider_user_id: Mapped[str] = mapped_column(String(255))
    provider_email: Mapped[str | None] = mapped_column(String(255))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Indexes and Unique Constraints
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="oauth_accounts")
