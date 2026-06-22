import uuid
import datetime
from sqlalchemy import select, delete
from src.models.two_factor import TwoFactorBackupCode
from src.repositories.base import TenantScopedRepository

class TwoFactorRepository(TenantScopedRepository):
    async def create_codes(self, user_id: uuid.UUID, code_hashes: list[str]) -> list[TwoFactorBackupCode]:
        codes = [
            TwoFactorBackupCode(
                user_id=user_id,
                tenant_id=self.tenant_id,
                code_hash=code_hash,
                is_used=False
            ) for code_hash in code_hashes
        ]
        self.db.add_all(codes)
        await self.db.flush()
        return codes

    async def get_unused_codes(self, user_id: uuid.UUID) -> list[TwoFactorBackupCode]:
        result = await self.db.execute(
            select(TwoFactorBackupCode).where(
                TwoFactorBackupCode.user_id == user_id,
                TwoFactorBackupCode.tenant_id == self.tenant_id,
                TwoFactorBackupCode.is_used == False
            )
        )
        return list(result.scalars().all())

    async def use_code(self, code: TwoFactorBackupCode) -> TwoFactorBackupCode:
        if code.tenant_id != self.tenant_id:
            raise ValueError("Cross-tenant backup code access blocked.")
        code.is_used = True
        code.used_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.add(code)
        await self.db.flush()
        return code

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(TwoFactorBackupCode).where(
                TwoFactorBackupCode.user_id == user_id,
                TwoFactorBackupCode.tenant_id == self.tenant_id
            )
        )
        await self.db.flush()
