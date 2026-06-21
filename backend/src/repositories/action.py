import uuid
from typing import Sequence
from sqlalchemy import select
from src.repositories.base import TenantScopedRepository
from src.models.action import Action

class ActionRepository(TenantScopedRepository):
    async def get_all(self) -> Sequence[Action]:
        result = await self.db.execute(select(Action).where(Action.tenant_id == self.tenant_id))
        return result.scalars().all()
        
    async def get_by_id(self, action_id: uuid.UUID) -> Action | None:
        result = await self.db.execute(select(Action).where(Action.id == action_id, Action.tenant_id == self.tenant_id))
        return result.scalar_one_or_none()
        
    def add(self, action: Action) -> None:
        self.db.add(action)
        
    async def delete(self, action: Action) -> None:
        await self.db.delete(action)
