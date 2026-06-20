import uuid
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.tenant import Tenant, TenantApiKey
from src.repositories.base import BaseRepository

class TenantRepository(BaseRepository):
    async def create(self, name: str, rate_limit_rpm: int = 1000) -> Tenant:
        tenant = Tenant(
            name=name,
            rate_limit_rpm=rate_limit_rpm
        )
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def get_by_api_key_hash(self, api_key_hash: str) -> Tenant | None:
        result = await self.db.execute(
            select(Tenant)
            .join(TenantApiKey, TenantApiKey.tenant_id == Tenant.id)
            .where(TenantApiKey.api_key_hash == api_key_hash)
        )
        return result.scalar_one_or_none()

    async def create_api_key(self, tenant_id: uuid.UUID, name: str, key_prefix: str, api_key_hash: str) -> TenantApiKey:
        api_key = TenantApiKey(
            tenant_id=tenant_id,
            name=name,
            key_prefix=key_prefix,
            api_key_hash=api_key_hash
        )
        self.db.add(api_key)
        await self.db.flush()
        return api_key

    async def get_api_keys(self, tenant_id: uuid.UUID) -> list[TenantApiKey]:
        result = await self.db.execute(
            select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def delete_api_key(self, tenant_id: uuid.UUID, api_key_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            delete(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id, TenantApiKey.id == api_key_id)
        )
        await self.db.flush()
        return result.rowcount > 0

    # --- Team Management ---

    async def get_members(self, tenant_id: uuid.UUID) -> list["User"]:
        from src.models.user import User
        result = await self.db.execute(
            select(User).where(User.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def remove_member(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        from src.models.user import User
        result = await self.db.execute(
            delete(User).where(User.tenant_id == tenant_id, User.id == user_id)
        )
        await self.db.flush()
        return result.rowcount > 0

    async def create_invite(self, tenant_id: uuid.UUID, email: str, role: str, token_hash: str, expires_at: datetime) -> "OrganizationInvite":
        from src.models.tenant import OrganizationInvite
        invite = OrganizationInvite(
            tenant_id=tenant_id,
            email=email,
            role=role,
            token_hash=token_hash,
            expires_at=expires_at
        )
        self.db.add(invite)
        await self.db.flush()
        return invite

    async def get_invites(self, tenant_id: uuid.UUID) -> list["OrganizationInvite"]:
        from src.models.tenant import OrganizationInvite
        result = await self.db.execute(
            select(OrganizationInvite).where(OrganizationInvite.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def get_invite_by_hash(self, token_hash: str) -> "OrganizationInvite | None":
        from src.models.tenant import OrganizationInvite
        result = await self.db.execute(
            select(OrganizationInvite).where(OrganizationInvite.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def delete_invite(self, invite_id: uuid.UUID) -> bool:
        from src.models.tenant import OrganizationInvite
        result = await self.db.execute(
            delete(OrganizationInvite).where(OrganizationInvite.id == invite_id)
        )
        await self.db.flush()
        return result.rowcount > 0
