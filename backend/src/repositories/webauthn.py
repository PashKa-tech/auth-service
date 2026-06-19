import uuid
from sqlalchemy import select, update, delete
from src.models.webauthn import WebAuthnCredential
from src.repositories.base import TenantScopedRepository

class WebAuthnRepository(TenantScopedRepository):
    async def create(
        self,
        user_id: uuid.UUID,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int,
        transports: str | None,
        name: str = "Passkey"
    ) -> WebAuthnCredential:
        credential = WebAuthnCredential(
            tenant_id=self.tenant_id,
            user_id=user_id,
            credential_id=credential_id,
            public_key=public_key,
            sign_count=sign_count,
            transports=transports,
            name=name
        )
        self.db.add(credential)
        await self.db.flush()
        return credential

    async def get_by_credential_id(self, credential_id: bytes) -> WebAuthnCredential | None:
        result = await self.db.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.credential_id == credential_id,
                WebAuthnCredential.tenant_id == self.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: uuid.UUID) -> list[WebAuthnCredential]:
        result = await self.db.execute(
            select(WebAuthnCredential).where(
                WebAuthnCredential.user_id == user_id,
                WebAuthnCredential.tenant_id == self.tenant_id
            ).order_by(WebAuthnCredential.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_sign_count(self, id: uuid.UUID, sign_count: int) -> None:
        await self.db.execute(
            update(WebAuthnCredential).where(
                WebAuthnCredential.id == id,
                WebAuthnCredential.tenant_id == self.tenant_id
            ).values(sign_count=sign_count)
        )
        await self.db.flush()

    async def delete(self, id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            delete(WebAuthnCredential).where(
                WebAuthnCredential.id == id,
                WebAuthnCredential.user_id == user_id,
                WebAuthnCredential.tenant_id == self.tenant_id
            )
        )
        await self.db.flush()
        return result.rowcount > 0
