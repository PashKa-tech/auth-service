import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.repositories.base import TenantScopedRepository
from src.models.rbac import Role, UserRole, RolePermission

class RbacRepository(TenantScopedRepository):
    async def get_all_roles(self) -> Sequence[Role]:
        result = await self.db.execute(
            select(Role)
            .where(Role.tenant_id == self.tenant_id)
            .options(selectinload(Role.permissions))
        )
        return result.scalars().all()
        
    async def get_role_by_name(self, name: str) -> Role | None:
        result = await self.db.execute(
            select(Role).where(Role.tenant_id == self.tenant_id, Role.name == name)
        )
        return result.scalar_one_or_none()
        
    async def get_role_by_id(self, role_id: uuid.UUID) -> Role | None:
        result = await self.db.execute(
            select(Role).where(Role.tenant_id == self.tenant_id, Role.id == role_id)
        )
        return result.scalar_one_or_none()
        
    def add_role(self, role: Role) -> None:
        self.db.add(role)
        
    def add_role_permission(self, rp: RolePermission) -> None:
        self.db.add(rp)
        
    async def delete_role(self, role: Role) -> None:
        await self.db.delete(role)
        
    async def get_user_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> UserRole | None:
        result = await self.db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        return result.scalar_one_or_none()
        
    def add_user_role(self, ur: UserRole) -> None:
        self.db.add(ur)
        
    async def delete_user_role(self, ur: UserRole) -> None:
        await self.db.delete(ur)
