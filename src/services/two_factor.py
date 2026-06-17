import uuid
from src.models.user import User
from src.repositories.user import UserRepository
from src.repositories.two_factor import TwoFactorRepository
from src.core.totp import (
    generate_totp_secret,
    get_provisioning_uri,
    verify_totp_code,
    encrypt_secret,
    decrypt_secret,
    generate_backup_codes,
    hash_backup_code
)

class TwoFactorService:
    def __init__(self, user_repo: UserRepository, two_factor_repo: TwoFactorRepository):
        self.user_repo = user_repo
        self.two_factor_repo = two_factor_repo

    async def setup_2fa(self, user: User) -> dict:
        """Initialize 2FA setup: generate temporary secret and backup codes."""
        # Check user belongs to current tenant
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA setup attempt blocked.")

        # Generate TOTP secret
        secret = generate_totp_secret()
        encrypted_secret = encrypt_secret(secret)
        
        # Save temporary encrypted secret (do not enable 2FA yet)
        user.totp_secret_encrypted = encrypted_secret
        await self.user_repo.update(user)

        # Regenerate backup codes (clear old ones)
        await self.two_factor_repo.delete_all_for_user(user.id)
        raw_backup_codes = generate_backup_codes()
        code_hashes = [hash_backup_code(code) for code in raw_backup_codes]
        await self.two_factor_repo.create_codes(user.id, code_hashes)

        # Get QR provisioning URI
        uri = get_provisioning_uri(secret, user.email)

        return {
            "totp_secret": secret,
            "provisioning_uri": uri,
            "backup_codes": raw_backup_codes
        }

    async def confirm_setup(self, user: User, totp_code: str) -> bool:
        """Confirm 2FA setup using a valid TOTP code to enable it."""
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA confirmation attempt blocked.")

        if not user.totp_secret_encrypted:
            return False

        # Decrypt secret and verify code
        secret = decrypt_secret(user.totp_secret_encrypted)
        if not verify_totp_code(secret, totp_code):
            return False

        # Enable 2FA
        user.is_two_factor_enabled = True
        await self.user_repo.update(user)
        return True

    async def verify_2fa(self, user: User, code: str) -> bool:
        """Verify 2FA code (either current TOTP or an unused backup code)."""
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA verification attempt blocked.")

        if not user.is_two_factor_enabled:
            return False

        # 1. Try TOTP code first
        if user.totp_secret_encrypted:
            secret = decrypt_secret(user.totp_secret_encrypted)
            if verify_totp_code(secret, code):
                return True

        # 2. Try Backup code
        code_hash = hash_backup_code(code)
        unused_codes = await self.two_factor_repo.get_unused_codes(user.id)
        for backup_code in unused_codes:
            if backup_code.code_hash == code_hash:
                # Mark backup code as used
                await self.two_factor_repo.use_code(backup_code)
                return True

        return False

    async def regenerate_backup_codes(self, user: User) -> list[str]:
        """Regenerate backup codes for the user if 2FA is active."""
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA regeneration attempt blocked.")

        if not user.is_two_factor_enabled:
            raise ValueError("2FA is not enabled for this user.")

        await self.two_factor_repo.delete_all_for_user(user.id)
        raw_backup_codes = generate_backup_codes()
        code_hashes = [hash_backup_code(code) for code in raw_backup_codes]
        await self.two_factor_repo.create_codes(user.id, code_hashes)
        return raw_backup_codes

    async def disable_2fa(self, user: User) -> None:
        """Disable 2FA and clear all 2FA parameters."""
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA disable attempt blocked.")

        user.is_two_factor_enabled = False
        user.totp_secret_encrypted = None
        await self.user_repo.update(user)

        # Clear backup codes
        await self.two_factor_repo.delete_all_for_user(user.id)
        
