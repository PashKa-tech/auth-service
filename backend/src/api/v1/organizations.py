import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from src.api.deps import get_current_user, get_tenant_service, RoleChecker, requires_fresh_auth, resolve_tenant
from src.models.user import User
from src.services.tenant import TenantService
from src.database import get_db

admin_only = RoleChecker(["admin", "superadmin"])
from pydantic import BaseModel

router = APIRouter()

from src.schemas.common import UnifiedResponse

class CreateApiKeyRequest(BaseModel):
    name: str

@router.get("/current", response_model=UnifiedResponse)
async def get_current_organization(
    current_user: User = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    tenant = await tenant_service.get_current_tenant()
    return UnifiedResponse(success=True, data={
        "id": str(tenant.id),
        "name": tenant.name,
        "rate_limit_rpm": tenant.rate_limit_rpm,
        "created_at": tenant.created_at.isoformat()
    })

@router.get("/api-keys", response_model=UnifiedResponse)
async def list_api_keys(
    current_user: User = Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    keys = await tenant_service.get_api_keys()
    formatted_keys = []
    for key in keys:
        formatted_keys.append({
            "id": str(key.id),
            "name": key.name,
            "key_prefix": key.key_prefix,
            "created_at": key.created_at.isoformat(),
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None
        })
    return UnifiedResponse(success=True, data=formatted_keys)

@router.post("/api-keys", response_model=UnifiedResponse)
async def create_api_key(
    req: CreateApiKeyRequest,
    current_user: User = Depends(requires_fresh_auth), # Require step-up to generate keys
    _=Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    api_key, raw_secret = await tenant_service.create_api_key(req.name, current_user.id)
    
    return UnifiedResponse(success=True, message="API Key generated. Save it now, it will not be shown again.", data={
        "id": str(api_key.id),
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "raw_secret": raw_secret # THIS IS THE ONLY TIME IT'S RETURNED!
    })

@router.delete("/api-keys/{key_id}", response_model=UnifiedResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(requires_fresh_auth),
    _=Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):

    success = await tenant_service.delete_api_key(key_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
    return UnifiedResponse(success=True, message="API Key revoked successfully")

# --- Team Management ---

class InviteRequest(BaseModel):
    email: str
    role: str

@router.get("/members", response_model=UnifiedResponse)
async def list_members(
    current_user: User = Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    members = await tenant_service.get_members()
    data = []
    for m in members:
        data.append({
            "id": str(m.id),
            "email": m.email,
            "role": m.role,
            "created_at": m.created_at.isoformat()
        })
    return UnifiedResponse(success=True, data=data)

@router.delete("/members/{user_id}", response_model=UnifiedResponse)
async def remove_member(
    user_id: uuid.UUID,
    current_user: User = Depends(requires_fresh_auth),
    _=Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    success = await tenant_service.remove_member(user_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    
    return UnifiedResponse(success=True, message="Member removed")

@router.get("/invites", response_model=UnifiedResponse)
async def list_invites(
    current_user: User = Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    invites = await tenant_service.get_invites()
    data = []
    for i in invites:
        data.append({
            "id": str(i.id),
            "email": i.email,
            "role": i.role,
            "expires_at": i.expires_at.isoformat(),
            "created_at": i.created_at.isoformat()
        })
    return UnifiedResponse(success=True, data=data)

@router.post("/invites", response_model=UnifiedResponse)
async def create_invite(
    req: InviteRequest,
    current_user: User = Depends(requires_fresh_auth),
    _=Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    try:
        await tenant_service.create_invite(req.email, req.role, current_user.id)
        return UnifiedResponse(success=True, message="Invitation sent successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/invites/{invite_id}", response_model=UnifiedResponse)
async def delete_invite(
    invite_id: uuid.UUID,
    current_user: User = Depends(requires_fresh_auth),
    _=Depends(RoleChecker(["admin"])),
    tenant_service: TenantService = Depends(get_tenant_service)
):

    success = await tenant_service.delete_invite(invite_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    
    return UnifiedResponse(success=True, message="Invitation revoked")

class AcceptInviteRequest(BaseModel):
    token: str
    password: str

from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db

@router.post("/invites/accept", response_model=UnifiedResponse)
async def accept_invite(
    req: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db)
) -> UnifiedResponse:
    import hashlib
    from datetime import datetime, timezone
    from src.models.tenant import OrganizationInvite
    from src.models.user import User as DBUser
    from src.core.security import hash_password
    from sqlalchemy import select
    
    token_hash = hashlib.sha256(req.token.encode("utf-8")).hexdigest()
    
    result = await db.execute(
        select(OrganizationInvite).where(OrganizationInvite.token_hash == token_hash)
    )
    invite = result.scalar_one_or_none()
    
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invitation token")
        
    if invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has expired")

    # Check if user already exists in this tenant
    res_user = await db.execute(
        select(DBUser).where(DBUser.tenant_id == invite.tenant_id, DBUser.email == invite.email)
    )
    if res_user.scalar_one_or_none():
        # They are already a member! Just delete the invite.
        await db.delete(invite)
        await db.commit()
        return UnifiedResponse(success=True, message="You are already a member of this organization. You can now login.")

    # Create the user
    password_hash = await hash_password(req.password)
    new_user = DBUser(
        tenant_id=invite.tenant_id,
        email=invite.email,
        password_hash=password_hash,
        role=invite.role,
        is_verified=True # Email is verified because they received the invite
    )
    db.add(new_user)
    
    # Delete the invite
    await db.delete(invite)
    await db.commit()
    
    return UnifiedResponse(success=True, message="Invitation accepted successfully. You can now login.")

from src.database import get_db

@router.get("/{tenant_id}/branding", response_model=UnifiedResponse)
async def get_tenant_branding(
    tenant_id: uuid.UUID,
    db: Any = Depends(get_db)
):
    """Get public branding configuration for a tenant."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.models.tenant import Tenant
    session: AsyncSession = db
    
    res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    return UnifiedResponse(success=True, data={
        "name": tenant.name,
        "logo_url": tenant.logo_url,
        "primary_color": tenant.primary_color,
        "font_family": tenant.font_family
    })

from pydantic import BaseModel
from typing import Optional

class TenantSettingsUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    font_family: Optional[str] = None
    pre_login_webhook_url: Optional[str] = None

@router.put("/current/settings", response_model=UnifiedResponse)
async def update_tenant_settings(
    body: TenantSettingsUpdate,
    db: Any = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: Any = Depends(admin_only)
):
    """Update tenant settings (Branding, Webhooks). Requires admin."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.models.tenant import Tenant
    session: AsyncSession = db
    
    res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    if body.name is not None:
        tenant.name = body.name
    if body.logo_url is not None:
        tenant.logo_url = body.logo_url
    if body.primary_color is not None:
        tenant.primary_color = body.primary_color
    if body.font_family is not None:
        tenant.font_family = body.font_family
    if body.pre_login_webhook_url is not None:
        tenant.pre_login_webhook_url = body.pre_login_webhook_url
        
    await session.commit()
    
    return UnifiedResponse(success=True, data={
        "name": tenant.name,
        "logo_url": tenant.logo_url,
        "primary_color": tenant.primary_color,
        "font_family": tenant.font_family,
        "pre_login_webhook_url": tenant.pre_login_webhook_url
    })
