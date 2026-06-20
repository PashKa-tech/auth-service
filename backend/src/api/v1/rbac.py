from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from pydantic import BaseModel
import uuid

from src.database import get_db
from src.api.deps import get_current_user, resolve_tenant, RoleChecker
from src.schemas.common import UnifiedResponse
from src.models.user import User
from src.models.rbac import Role, RolePermission

router = APIRouter()

# Restrict to admins only
admin_only = RoleChecker(["admin", "manager"])

@router.get("/roles")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """List all roles for the tenant."""
    result = await db.execute(
        select(Role)
        .where(Role.tenant_id == tenant_id)
        .options(selectinload(Role.permissions))
    )
    roles = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_system": r.is_system,
            "permissions": [p.permission for p in r.permissions]
        }
        for r in roles
    ]

@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(
    name: str,
    description: str = "",
    permissions: list[str] = [],
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Create a new custom role."""
    # Check if role exists
    existing = await db.execute(select(Role).where(Role.tenant_id == tenant_id, Role.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role already exists")
        
    role = Role(
        tenant_id=tenant_id,
        name=name,
        description=description,
        is_system=False
    )
    db.add(role)
    await db.flush()
    
    for perm in permissions:
        rp = RolePermission(role_id=role.id, permission=perm)
        db.add(rp)
        
    await db.commit()
    return {"message": "Role created successfully", "role_id": role.id}

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Delete a custom role."""
    result = await db.execute(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system role")
        
    await db.delete(role)
    await db.commit()
    return {"message": "Role deleted successfully"}

class RoleAssignRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID

@router.post("/roles/assign", response_model=UnifiedResponse)
async def assign_role(
    body: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Assign a role to a user."""
    from src.models.rbac import UserRole
    
    # Verify user belongs to tenant
    user_res = await db.execute(select(User).where(User.id == body.user_id, User.tenant_id == tenant_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in tenant")

    # Verify role belongs to tenant
    role_res = await db.execute(select(Role).where(Role.id == body.role_id, Role.tenant_id == tenant_id))
    role = role_res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # Check if already assigned
    ur_res = await db.execute(select(UserRole).where(UserRole.user_id == body.user_id, UserRole.role_id == body.role_id))
    if ur_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already has this role")
        
    ur = UserRole(user_id=body.user_id, role_id=body.role_id)
    db.add(ur)
    await db.commit()
    
    return UnifiedResponse(success=True, message="Role assigned successfully")

@router.delete("/roles/assign/{user_id}/{role_id}", response_model=UnifiedResponse)
async def unassign_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Unassign a role from a user."""
    from src.models.rbac import UserRole
    ur_res = await db.execute(
        select(UserRole)
        .join(Role, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, UserRole.role_id == role_id, Role.tenant_id == tenant_id)
    )
    ur = ur_res.scalar_one_or_none()
    
    if not ur:
        raise HTTPException(status_code=404, detail="Role assignment not found")
        
    await db.delete(ur)
    await db.commit()
    
    return UnifiedResponse(success=True, message="Role unassigned successfully")
