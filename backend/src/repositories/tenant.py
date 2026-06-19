import uuid
from sqlalchemy import select
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
            select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id, TenantApiKey.id == api_key_id)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return False
        
        await self.db.delete(api_key)
        await self.db.flush()
        return True
