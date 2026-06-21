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

from src.api.deps import get_rbac_repository, get_user_repository
from src.repositories.rbac import RbacRepository
from src.repositories.user import UserRepository

@router.get("/roles")
async def list_roles(
    repo: RbacRepository = Depends(get_rbac_repository),
    current_user: User = Depends(admin_only)
):
    """List all roles for the tenant."""
    roles = await repo.get_all_roles()
    
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
    repo: RbacRepository = Depends(get_rbac_repository),
    current_user: User = Depends(admin_only)
):
    """Create a new custom role."""
    # Check if role exists
    existing = await repo.get_role_by_name(name)
    if existing:
        raise HTTPException(status_code=400, detail="Role already exists")
        
    role = Role(
        tenant_id=repo.tenant_id,
        name=name,
        description=description,
        is_system=False
    )
    repo.add_role(role)
    await repo.db.flush()
    
    for perm in permissions:
        rp = RolePermission(role_id=role.id, permission=perm)
        repo.add_role_permission(rp)
        
    await repo.db.commit()
    return {"message": "Role created successfully", "role_id": role.id}

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    repo: RbacRepository = Depends(get_rbac_repository),
    current_user: User = Depends(admin_only)
):
    """Delete a custom role."""
    role = await repo.get_role_by_id(role_id)
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system role")
        
    await repo.delete_role(role)
    await repo.db.commit()
    return {"message": "Role deleted successfully"}

class RoleAssignRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID

@router.post("/roles/assign", response_model=UnifiedResponse)
async def assign_role(
    body: RoleAssignRequest,
    repo: RbacRepository = Depends(get_rbac_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    current_user: User = Depends(admin_only)
):
    """Assign a role to a user."""
    from src.models.rbac import UserRole
    
    # Verify user belongs to tenant
    user = await user_repo.get_by_id(body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found in tenant")

    # Verify role belongs to tenant
    role = await repo.get_role_by_id(body.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # Check if already assigned
    ur = await repo.get_user_role(body.user_id, body.role_id)
    if ur:
        raise HTTPException(status_code=400, detail="User already has this role")
        
    ur = UserRole(user_id=body.user_id, role_id=body.role_id)
    repo.add_user_role(ur)
    await repo.db.commit()
    
    return UnifiedResponse(success=True, message="Role assigned successfully")

@router.delete("/roles/assign/{user_id}/{role_id}", response_model=UnifiedResponse)
async def unassign_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    repo: RbacRepository = Depends(get_rbac_repository),
    current_user: User = Depends(admin_only)
):
    """Unassign a role from a user."""
    ur = await repo.get_user_role(user_id, role_id)
    
    if not ur:
        raise HTTPException(status_code=404, detail="Role assignment not found")
        
    await repo.delete_user_role(ur)
    await repo.db.commit()
    
    return UnifiedResponse(success=True, message="Role unassigned successfully")
