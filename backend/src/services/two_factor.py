import uuid
from fastapi import BackgroundTasks
from src.models.user import User
from src.repositories.user import UserRepository
from src.repositories.two_factor import TwoFactorRepository
from src.services.email import EmailService
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
    def __init__(self, user_repo: UserRepository, two_factor_repo: TwoFactorRepository, email_service: EmailService, background_tasks: BackgroundTasks):
        self.user_repo = user_repo
        self.two_factor_repo = two_factor_repo
        self.email_service = email_service
        self.background_tasks = background_tasks

    async def setup_2fa(self, user: User) -> dict:
        """Initialize 2FA setup: generate temporary secret and backup codes."""
        # Check user belongs to current tenant
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA setup attempt blocked.")

        if user.is_two_factor_enabled:
            raise ValueError("2FA is already enabled.")

        if user.totp_secret_encrypted:
            from src.core.logging import logger
            logger.warning(f"User {user.id} has an unconfirmed pending 2FA setup. Overwriting it.")

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

        await self.user_repo.db.commit()
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

        # Send email notification
        self.background_tasks.add_task(
            self.email_service.send_email,
            to_email=user.email,
            subject="Двухфакторная аутентификация включена - Auth Service",
            body="""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="color: #10b981;">Безопасность вашего аккаунта обновлена</h2>
                <p>Здравствуйте,</p>
                <p>На вашем аккаунте была успешно <strong>включена двухфакторная аутентификация (2FA)</strong>.</p>
                <p>При каждом входе в систему теперь потребуется вводить проверочный код из вашего приложения аутентификации.</p>
                <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
                <p style="font-size: 0.85rem; color: #6b7280;">Если вы не совершали этого действия, пожалуйста, незамедлительно свяжитесь с поддержкой.</p>
            </div>
            """
        )
        await self.user_repo.db.commit()
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
                from src.core.redis import init_redis
                redis_client = await init_redis()
                key = f"totp_used:{user.id}:{code.strip()}"
                is_unique = await redis_client.set(key, "1", ex=60, nx=True)
                if not is_unique:
                    return False
                return True

        # 2. Try Backup code
        code_hash = hash_backup_code(code)
        unused_codes = await self.two_factor_repo.get_unused_codes(user.id)
        for backup_code in unused_codes:
            if backup_code.code_hash == code_hash:
                # Mark backup code as used
                await self.two_factor_repo.use_code(backup_code)
                await self.user_repo.db.commit()
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

        # Send email notification
        self.background_tasks.add_task(
            self.email_service.send_email,
            to_email=user.email,
            subject="Резервные коды 2FA обновлены - Auth Service",
            body="""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="color: #f59e0b;">Обновление резервных кодов</h2>
                <p>Здравствуйте,</p>
                <p>Резервные коды двухфакторной аутентификации для вашего аккаунта были <strong>перегенерированы</strong>.</p>
                <p>Все старые резервные коды стали недействительными.</p>
                <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
                <p style="font-size: 0.85rem; color: #6b7280;">Если вы не запрашивали перегенерацию, ваш аккаунт может быть скомпрометирован. Пожалуйста, смените пароль и обратитесь в поддержку.</p>
            </div>
            """
        )
        await self.user_repo.db.commit()
        return raw_backup_codes

    async def disable_2fa(self, user: User, password: str | None = None, totp_code: str | None = None) -> bool:
        """Disable 2FA and clear all 2FA parameters."""
        if user.tenant_id != self.user_repo.tenant_id:
            raise ValueError("Cross-tenant 2FA disable attempt blocked.")

        if not password and not totp_code:
            return False

        if password:
            from src.core.security import verify_password
            if not await verify_password(password, user.password_hash):
                return False
                
        if totp_code:
            if not await self.verify_2fa(user, totp_code):
                return False

        user.is_two_factor_enabled = False
        user.totp_secret_encrypted = None
        await self.user_repo.update(user)

        # Clear backup codes
        await self.two_factor_repo.delete_all_for_user(user.id)

        # Send email notification
        self.background_tasks.add_task(
            self.email_service.send_email,
            to_email=user.email,
            subject="Двухфакторная аутентификация отключена - Auth Service",
            body="""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="color: #ef4444;">Предупреждение безопасности</h2>
                <p>Здравствуйте,</p>
                <p>На вашем аккаунте была <strong>отключена двухфакторная аутентификация (2FA)</strong>.</p>
                <p>Уровень защиты вашего аккаунта снижен, теперь для входа требуется только пароль.</p>
                <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
                <p style="font-size: 0.85rem; color: #6b7280;">Если вы не совершали этого действия, пожалуйста, немедленно свяжитесь с поддержкой.</p>
            </div>
            """
        )
        await self.user_repo.db.commit()
        return True
