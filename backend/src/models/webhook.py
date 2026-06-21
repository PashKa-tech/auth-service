import uuid
from datetime import datetime
from typing import Any, List, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.tenant import Tenant

class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    secret_key: Mapped[str] = mapped_column(String(255))
    events_list: Mapped[List[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="webhook_endpoints")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(back_populates="endpoint", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="pending") # pending, success, failed
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    endpoint: Mapped["WebhookEndpoint"] = relationship(back_populates="deliveries")
