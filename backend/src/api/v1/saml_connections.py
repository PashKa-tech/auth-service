from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from src.database import get_db
from src.api.deps import resolve_tenant, RoleChecker
from src.models.user import User
from src.models.saml import SamlConnection
from src.schemas.common import UnifiedResponse

router = APIRouter()
admin_only = RoleChecker(["admin", "manager"])

class SamlConnectionCreate(BaseModel):
    name: str
    idp_entity_id: str
    sso_url: str
    x509_cert: str
    email_attribute: str = "email"
    first_name_attribute: Optional[str] = None
    last_name_attribute: Optional[str] = None
    auto_provision: bool = True

@router.get("", response_model=UnifiedResponse)
async def list_saml_connections(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """List all SAML Connections for the tenant."""
    res = await db.execute(select(SamlConnection).where(SamlConnection.tenant_id == tenant_id))
    connections = res.scalars().all()
    
    return UnifiedResponse(success=True, data=[
        {
            "id": c.id,
            "name": c.name,
            "idp_entity_id": c.idp_entity_id,
            "sso_url": c.sso_url,
            "email_attribute": c.email_attribute,
            "auto_provision": c.auto_provision,
            "is_active": c.is_active
        } for c in connections
    ])

@router.post("", response_model=UnifiedResponse)
async def create_saml_connection(
    body: SamlConnectionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Create a new SAML Connection."""
    connection = SamlConnection(
        tenant_id=tenant_id,
        name=body.name,
        idp_entity_id=body.idp_entity_id,
        sso_url=body.sso_url,
        x509_cert=body.x509_cert,
        email_attribute=body.email_attribute,
        first_name_attribute=body.first_name_attribute,
        last_name_attribute=body.last_name_attribute,
        auto_provision=body.auto_provision,
        is_active=True
    )
    db.add(connection)
    await db.commit()
    
    return UnifiedResponse(success=True, data={
        "id": connection.id,
        "name": connection.name,
        "idp_entity_id": connection.idp_entity_id,
        "sso_url": connection.sso_url
    })

@router.delete("/{connection_id}", response_model=UnifiedResponse)
async def delete_saml_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Delete a SAML Connection."""
    res = await db.execute(select(SamlConnection).where(SamlConnection.id == connection_id, SamlConnection.tenant_id == tenant_id))
    connection = res.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    await db.delete(connection)
    await db.commit()
    
    return UnifiedResponse(success=True, message="Connection deleted successfully")
