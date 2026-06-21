from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
import uuid
from typing import List, Optional, Dict, Any

from src.database import get_db
from src.api.deps import resolve_tenant
from src.models.user import User
from src.core.security import hash_password

router = APIRouter()

# --- SCIM Schemas ---
# Note: SCIM schemas are complex and nested. We implement a minimal subset for provision/deprovision.
class SCIMName(BaseModel):
    formatted: Optional[str] = None
    familyName: Optional[str] = None
    givenName: Optional[str] = None

class SCIMEmail(BaseModel):
    value: EmailStr
    primary: Optional[bool] = True

class SCIMUserCreate(BaseModel):
    schemas: List[str]
    userName: EmailStr
    name: Optional[SCIMName] = None
    emails: List[SCIMEmail]
    active: Optional[bool] = True
    password: Optional[str] = None

class SCIMUserUpdate(BaseModel):
    schemas: List[str]
    userName: Optional[EmailStr] = None
    active: Optional[bool] = None
    name: Optional[SCIMName] = None

def serialize_scim_user(user: User) -> dict:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "name": {
            "formatted": user.email.split('@')[0]
        },
        "emails": [
            {
                "value": user.email,
                "primary": True
            }
        ],
        "active": user.is_active,
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat(),
            "lastModified": user.updated_at.isoformat()
        }
    }

# --- Endpoints ---

from fastapi import Query
@router.get("/Users", status_code=status.HTTP_200_OK)
async def list_users(
    request: Request,
    startIndex: int = Query(1, ge=1),
    count: int = Query(50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """SCIM: List Users"""
    offset = startIndex - 1
    
    # Get total count
    from sqlalchemy import func
    count_res = await db.execute(select(func.count(User.id)).where(User.tenant_id == tenant_id))
    total_results = count_res.scalar_one()

    # Get paginated results
    res = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id)
        .order_by(User.created_at)
        .offset(offset)
        .limit(count)
    )
    users = res.scalars().all()
    
    resources = [serialize_scim_user(u) for u in users]
    
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total_results,
        "startIndex": startIndex,
        "itemsPerPage": count,
        "Resources": resources
    }

@router.get("/Users/{user_id}", status_code=status.HTTP_200_OK)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """SCIM: Get User by ID"""
    res = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return serialize_scim_user(user)

@router.post("/Users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: SCIMUserCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """SCIM: Provision a new User"""
    from sqlalchemy import func
    email = body.userName.lower()
    
    # Check if exists
    res = await db.execute(select(User).where(func.lower(User.email) == email, User.tenant_id == tenant_id))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists")
        
    pwd_hash = await hash_password(body.password) if body.password else None
        
    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=pwd_hash,
        is_active=body.active if body.active is not None else True,
        is_verified=True, # SCIM provisioned users are assumed verified
        role="user"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return serialize_scim_user(user)

@router.put("/Users/{user_id}", status_code=status.HTTP_200_OK)
async def update_user(
    user_id: uuid.UUID,
    body: SCIMUserUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """SCIM: Update User attributes"""
    res = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if body.active is not None:
        user.is_active = body.active
        
    if body.userName:
        user.email = body.userName.lower()
        
    await db.commit()
    await db.refresh(user)
    
    return serialize_scim_user(user)

@router.delete("/Users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """SCIM: Delete / Deprovision User"""
    res = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant_id))
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    await db.delete(user)
    await db.commit()
    return None
