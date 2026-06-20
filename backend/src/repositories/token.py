import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update, delete, func
from src.models.token import RefreshToken, VerificationToken
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
            select(Session.id)
            .join(User, Session.user_id == User.id)
            .where(Session.id == session_id, User.tenant_id == self.tenant_id)
        )
        if not result.scalar_one_or_none():
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
            update(RefreshToken)
            .where(
                RefreshToken.id == token_id,
                RefreshToken.session_id.in_(
                    select(Session.id)
                    .join(User, Session.user_id == User.id)
                    .where(User.tenant_id == self.tenant_id)
                )
            )
            .values(is_revoked=True)
        )
        await self.db.flush()
        return result.rowcount > 0

    async def revoke_family(self, family_id: str) -> int:
        # Revoke all tokens in family
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

class VerificationTokenRepository(TenantScopedRepository):
    async def create_token(
        self,
        user_id: uuid.UUID,
        token_type: str,
        expires_at: datetime
    ) -> str:
        token_string = secrets.token_hex(32)
        
        # Verify user belongs to the tenant
        result = await self.db.execute(
            select(User.id)
            .where(User.id == user_id, User.tenant_id == self.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise ValueError("User not found in this tenant context.")
            
        token = VerificationToken(
            user_id=user_id,
            token=token_string,
            token_type=token_type,
            expires_at=expires_at
        )
        self.db.add(token)
        await self.db.flush()
        return token_string

    async def get_valid_token(self, token_string: str, token_type: str) -> VerificationToken | None:
        result = await self.db.execute(
            select(VerificationToken)
            .join(User, VerificationToken.user_id == User.id)
            .where(
                VerificationToken.token == token_string,
                VerificationToken.token_type == token_type,
                VerificationToken.expires_at > func.now(),
                User.tenant_id == self.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def delete_token(self, token_id: uuid.UUID) -> None:
        result = await self.db.execute(
            delete(VerificationToken)
            .where(
                VerificationToken.id == token_id,
                VerificationToken.user_id.in_(
                    select(User.id).where(User.tenant_id == self.tenant_id)
                )
            )
        )
        await self.db.flush()
