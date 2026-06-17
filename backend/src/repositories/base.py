from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

class TenantScopedRepository(BaseRepository):
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        super().__init__(db)
        self.tenant_id = tenant_id
