import uuid
from datetime import datetime
from sqlalchemy import select, update
from src.models.token import RefreshToken
from src.models.session import Session
from src.models.user import User
from src.repositories.base import TenantScopedRepository

class TokenRepository(TenantScopedRepository):
    async def create(
        self,
        session_id: uuid.UUID,
        token_hash: str,
        family_id: str,
        expires_at: datetime
    ) -> RefreshToken:
        # Verify session belongs to the tenant
        result = await self.db.execute(
            select(Session)
            .join(User, Session.user_id == User.id)
            .where(Session.id == session_id, User.tenant_id == self.tenant_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Session not found in this tenant context.")

        token = RefreshToken(
            session_id=session_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken)
            .join(Session, RefreshToken.session_id == Session.id)
            .join(User, Session.user_id == User.id)
            .where(RefreshToken.token_hash == token_hash, User.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(RefreshToken)
            .join(Session, RefreshToken.session_id == Session.id)
            .join(User, Session.user_id == User.id)
            .where(RefreshToken.id == token_id, User.tenant_id == self.tenant_id)
        )
        token = result.scalar_one_or_none()
        if not token:
            return False
        token.is_revoked = True
        self.db.add(token)
        await self.db.flush()
        return True

    async def revoke_family(self, family_id: str) -> int:
        # Revoke all tokens in family
        # We must filter by family_id and verify tenant_id by joining Session and User
        result = await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.is_revoked == False,
                RefreshToken.session_id.in_(
                    select(Session.id)
                    .join(User, Session.user_id == User.id)
                    .where(User.tenant_id == self.tenant_id)
                )
            )
            .values(is_revoked=True)
        )
        await self.db.flush()
        return result.rowcount
