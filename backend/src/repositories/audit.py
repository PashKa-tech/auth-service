import uuid
from sqlalchemy import select
from src.models.audit import AuditLog
from src.repositories.base import TenantScopedRepository

from src.database import async_session_factory
from src.core.logging import logger

async def write_audit_log_background(
    tenant_id: uuid.UUID,
    action: str,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    device_fingerprint: str | None = None,
    metadata_json: dict | None = None
):
    try:
        async with async_session_factory() as db:
            log = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                metadata_json=metadata_json
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to write background audit log: {e}")

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

    def create_background(
        self,
        background_tasks,
        action: str,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None,
        metadata_json: dict | None = None
    ):
        background_tasks.add_task(
            write_audit_log_background,
            self.tenant_id, action, user_id, ip_address, user_agent, device_fingerprint, metadata_json
        )

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
