import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Tuple
from fastapi import BackgroundTasks
from src.config import settings
from src.repositories.tenant import TenantRepository
from src.repositories.audit import AuditRepository
from src.services.email import EmailService
from src.models.tenant import Tenant, TenantApiKey, OrganizationInvite
from src.models.user import User

class TenantService:
    def __init__(self, tenant_repo: TenantRepository, audit_repo: AuditRepository, email_service: EmailService, background_tasks: BackgroundTasks):
        self.tenant_repo = tenant_repo
        self.audit_repo = audit_repo
        self.email_service = email_service
        self.background_tasks = background_tasks
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

    # --- Team Management ---

    async def get_members(self) -> list[User]:
        return await self.tenant_repo.get_members(self.tenant_id)

    async def remove_member(self, user_to_remove: uuid.UUID, admin_id: uuid.UUID) -> bool:
        success = await self.tenant_repo.remove_member(self.tenant_id, user_to_remove)
        if success:
            await self.audit_repo.create(
                action="member_removed",
                user_id=admin_id,
                metadata_json={"removed_user_id": str(user_to_remove)}
            )
        return success

    async def get_invites(self) -> list[OrganizationInvite]:
        return await self.tenant_repo.get_invites(self.tenant_id)

    async def create_invite(self, email: str, role: str, admin_id: uuid.UUID) -> OrganizationInvite:
        # Check if already a member
        members = await self.get_members()
        if any(m.email == email for m in members):
            raise ValueError("User is already a member of this organization")

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)

        invite = await self.tenant_repo.create_invite(
            tenant_id=self.tenant_id,
            email=email,
            role=role,
            token_hash=token_hash,
            expires_at=expires_at
        )

        tenant = await self.get_current_tenant()

        # Send email
        invite_url = f"{settings.FRONTEND_URL}/invite?token={raw_token}"
        self.background_tasks.add_task(
            self.email_service.send_email,
            to_email=email,
            subject=f"You have been invited to join {tenant.name}",
            body=f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>Organization Invitation</h2>
                <p>You have been invited to join <strong>{tenant.name}</strong> as a <strong>{role}</strong>.</p>
                <p>Click the link below to accept the invitation and set up your account:</p>
                <div style="margin: 30px 0;">
                    <a href="{invite_url}" style="background-color: #8b5cf6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Accept Invitation</a>
                </div>
                <p style="color: #6b7280; font-size: 0.875rem;">This link will expire in 7 days.</p>
            </div>
            """
        )

        await self.audit_repo.create(
            action="invite_created",
            user_id=admin_id,
            metadata_json={"invite_email": email, "role": role}
        )

        return invite

    async def delete_invite(self, invite_id: uuid.UUID, admin_id: uuid.UUID) -> bool:
        success = await self.tenant_repo.delete_invite(self.tenant_id, invite_id)
        if success:
            await self.audit_repo.create(
                action="invite_deleted",
                user_id=admin_id,
                metadata_json={"invite_id": str(invite_id)}
            )
        return success
