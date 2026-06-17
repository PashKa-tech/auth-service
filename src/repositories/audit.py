import uuid
from sqlalchemy import select
from src.models.audit import AuditLog
from src.repositories.base import TenantScopedRepository

class AuditRepository(TenantScopedRepository):
    async def create(
        self,
        action: str,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None,
        metadata_json: dict | None = None
    ) -> AuditLog:
        log = AuditLog(
            tenant_id=self.tenant_id,
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            metadata_json=metadata_json
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_by_tenant(self, limit: int = 50, offset: int = 0) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == self.tenant_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id, AuditLog.tenant_id == self.tenant_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
