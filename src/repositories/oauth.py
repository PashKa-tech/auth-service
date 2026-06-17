import uuid
from sqlalchemy import select
from src.models.oauth import OAuthAccount
from src.models.user import User
from src.repositories.base import TenantScopedRepository

class OAuthRepository(TenantScopedRepository):
    async def create(
        self,
        user_id: uuid.UUID,
        provider: str,
        provider_user_id: str,
        provider_email: str | None = None
    ) -> OAuthAccount:
        # Verify user belongs to this tenant
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == self.tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found in this tenant context.")

        oauth_account = OAuthAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=str(provider_user_id),
            provider_email=provider_email
        )
        self.db.add(oauth_account)
        await self.db.flush()
        return oauth_account

    async def get_by_provider_id(self, provider: str, provider_user_id: str) -> OAuthAccount | None:
        """Find OAuth link for a given provider and user ID within this tenant."""
        result = await self.db.execute(
            select(OAuthAccount)
            .join(User, OAuthAccount.user_id == User.id)
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == str(provider_user_id),
                User.tenant_id == self.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[OAuthAccount]:
        result = await self.db.execute(
            select(OAuthAccount)
            .join(User, OAuthAccount.user_id == User.id)
            .where(OAuthAccount.user_id == user_id, User.tenant_id == self.tenant_id)
        )
        return list(result.scalars().all())

    async def delete_by_provider(self, user_id: uuid.UUID, provider: str) -> bool:
        result = await self.db.execute(
            select(OAuthAccount)
            .join(User, OAuthAccount.user_id == User.id)
            .where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
                User.tenant_id == self.tenant_id
            )
        )
        oauth_account = result.scalar_one_or_none()
        if not oauth_account:
            return False
        await self.db.delete(oauth_account)
        await self.db.flush()
        return True
