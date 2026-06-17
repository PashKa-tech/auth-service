import uuid
from datetime import datetime
from sqlalchemy import select, update
from src.models.session import Session
from src.models.user import User
from src.repositories.base import TenantScopedRepository

class SessionRepository(TenantScopedRepository):
    async def create(
        self,
        user_id: uuid.UUID,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None
    ) -> Session:
        # Verify user belongs to the tenant first
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == self.tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found in this tenant context.")

        session = Session(
            user_id=user_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        result = await self.db.execute(
            select(Session)
            .join(User, Session.user_id == User.id)
            .where(Session.id == session_id, User.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_active_by_user(self, user_id: uuid.UUID) -> list[Session]:
        result = await self.db.execute(
            select(Session)
            .join(User, Session.user_id == User.id)
            .where(
                Session.user_id == user_id,
                User.tenant_id == self.tenant_id,
                Session.is_revoked == False,
                Session.expires_at > datetime.utcnow()
            )
        )
        return list(result.scalars().all())

    async def revoke(self, session_id: uuid.UUID) -> bool:
        # Check if the session exists and belongs to the tenant first
        session = await self.get_by_id(session_id)
        if not session:
            return False
        session.is_revoked = True
        self.db.add(session)
        await self.db.flush()
        return True

    async def revoke_all_by_user(self, user_id: uuid.UUID) -> int:
        # Revoke all sessions for user belonging to this tenant
        result = await self.db.execute(
            update(Session)
            .where(
                Session.user_id == user_id,
                Session.is_revoked == False,
                Session.user_id.in_(
                    select(User.id).where(User.id == user_id, User.tenant_id == self.tenant_id)
                )
            )
            .values(is_revoked=True)
        )
        await self.db.flush()
        return result.rowcount
