import uuid
import secrets
import hashlib
from typing import Tuple
from src.repositories.tenant import TenantRepository
from src.repositories.audit import AuditRepository
from src.models.tenant import Tenant, TenantApiKey

class TenantService:
    def __init__(self, tenant_repo: TenantRepository, audit_repo: AuditRepository):
        self.tenant_repo = tenant_repo
        self.audit_repo = audit_repo
        self.tenant_id = tenant_repo.tenant_id

    async def get_current_tenant(self) -> Tenant:
        return await self.tenant_repo.get_by_id(self.tenant_id)

    async def get_api_keys(self) -> list[TenantApiKey]:
        return await self.tenant_repo.get_api_keys(self.tenant_id)

    async def create_api_key(self, name: str, user_id: uuid.UUID) -> Tuple[TenantApiKey, str]:
        """
        Generate a new API Key for the tenant.
        Returns the TenantApiKey model and the raw secret string (which is only returned once).
        """
        raw_secret = secrets.token_hex(32)
        key_prefix = f"sk_test_{raw_secret[:8]}" # For simplicity, we use sk_test_ prefix
        full_api_key = f"{key_prefix}_{raw_secret}"
        
        # Hash the full api key using SHA-256 for storage
        api_key_hash = hashlib.sha256(full_api_key.encode("utf-8")).hexdigest()

        api_key = await self.tenant_repo.create_api_key(
            tenant_id=self.tenant_id,
            name=name,
            key_prefix=key_prefix,
            api_key_hash=api_key_hash
        )

        await self.audit_repo.create(
            action="api_key_created",
            user_id=user_id,
            metadata_json={"api_key_id": str(api_key.id), "name": name, "prefix": key_prefix}
        )

        return api_key, full_api_key

    async def delete_api_key(self, api_key_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Revoke an API Key."""
        success = await self.tenant_repo.delete_api_key(self.tenant_id, api_key_id)
        if success:
            await self.audit_repo.create(
                action="api_key_revoked",
                user_id=user_id,
                metadata_json={"api_key_id": str(api_key_id)}
            )
        return success
