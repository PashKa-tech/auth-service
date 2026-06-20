from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
import uuid
import secrets

from src.database import get_db
from src.api.deps import resolve_tenant, RoleChecker
from src.models.user import User
from src.models.m2m import OAuthApplication
from src.schemas.common import UnifiedResponse

router = APIRouter()
admin_only = RoleChecker(["admin", "manager"])

class OAuthAppCreate(BaseModel):
    name: str
    client_type: str = "confidential"
    redirect_uris: str = ""
    allowed_scopes: str = "read write"

class OAuthAppResponse(BaseModel):
    id: uuid.UUID
    name: str
    client_id: str
    client_type: str
    redirect_uris: str
    allowed_scopes: str

@router.get("", response_model=UnifiedResponse)
async def list_oauth_apps(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """List all OAuth Applications for the tenant."""
    res = await db.execute(select(OAuthApplication).where(OAuthApplication.tenant_id == tenant_id))
    apps = res.scalars().all()
    
    return UnifiedResponse(success=True, data=[
        {
            "id": app.id,
            "name": app.name,
            "client_id": app.client_id,
            "client_type": app.client_type,
            "redirect_uris": app.redirect_uris,
            "allowed_scopes": app.allowed_scopes
        } for app in apps
    ])

@router.post("", response_model=UnifiedResponse)
async def create_oauth_app(
    body: OAuthAppCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Create a new OAuth Application."""
    import hashlib
    client_id = secrets.token_urlsafe(24)
    client_secret_raw = secrets.token_urlsafe(48)
    client_secret_hash = hashlib.sha256(client_secret_raw.encode("utf-8")).hexdigest()
    
    app = OAuthApplication(
        tenant_id=tenant_id,
        name=body.name,
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        client_type=body.client_type,
        redirect_uris=body.redirect_uris,
        allowed_scopes=body.allowed_scopes
    )
    db.add(app)
    await db.commit()
    
    return UnifiedResponse(success=True, data={
        "id": app.id,
        "name": app.name,
        "client_id": app.client_id,
        "raw_secret": client_secret_raw,  # Only returned once!
        "client_type": app.client_type,
        "redirect_uris": app.redirect_uris,
        "allowed_scopes": app.allowed_scopes
    })

@router.delete("/{app_id}", response_model=UnifiedResponse)
async def delete_oauth_app(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Delete an OAuth Application."""
    res = await db.execute(select(OAuthApplication).where(OAuthApplication.id == app_id, OAuthApplication.tenant_id == tenant_id))
    app = res.scalar_one_or_none()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    await db.delete(app)
    await db.commit()
    
    return UnifiedResponse(success=True, message="Application deleted successfully")
