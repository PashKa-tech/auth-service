import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base

if TYPE_CHECKING:
    from src.models.tenant import Tenant

class SamlConnection(Base):
    __tablename__ = "saml_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100)) # e.g. "Okta Main"
    idp_entity_id: Mapped[str] = mapped_column(String(255))
    idp_sso_url: Mapped[str] = mapped_column(String(255))
    idp_x509_cert: Mapped[str] = mapped_column(Text)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    domain_mapping: Mapped[str | None] = mapped_column(String(255), unique=True, index=True) # e.g. "company.com"

    tenant: Mapped["Tenant"] = relationship()
