import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.tenant import Tenant
from src.repositories.base import BaseRepository

class TenantRepository(BaseRepository):
    async def create(self, name: str, api_key_hash: str, api_secret_hash: str, rate_limit_rpm: int = 1000) -> Tenant:
        tenant = Tenant(
            name=name,
            api_key=api_key_hash,
            api_secret_hash=api_secret_hash,
            rate_limit_rpm=rate_limit_rpm
        )
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def get_by_api_key_hash(self, api_key_hash: str) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.api_key == api_key_hash))
        return result.scalar_one_or_none()
