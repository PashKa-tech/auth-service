import uuid
from datetime import datetime, timedelta, timezone
from src.config import settings
from src.core.logging import logger

from src.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    create_mfa_token,
    verify_mfa_token
)
from src.core.fingerprint import calculate_device_fingerprint
from src.repositories.user import UserRepository
from src.repositories.session import SessionRepository
from src.repositories.token import TokenRepository, VerificationTokenRepository
from src.repositories.audit import AuditRepository
from src.repositories.oauth import OAuthRepository
from src.services.email import EmailService
from src.models.user import User
from src.models.session import Session
from src.core.metrics import LOGIN_COUNTER, REFRESH_COUNTER, ACTIVE_SESSIONS
from src.core.geoip import get_country_from_ip

class LoginResult:
    def __init__(
        self,
        requires_2fa: bool,
        mfa_token: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        session: Session | None = None
    ):
        self.requires_2fa = requires_2fa
        self.mfa_token = mfa_token
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.session = session

class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        token_repo: TokenRepository,
        audit_repo: AuditRepository,
        oauth_repo: OAuthRepository,
        verification_token_repo: VerificationTokenRepository,
        email_service: EmailService,
        background_tasks: "BackgroundTasks"
    ):
        self.user_repo = user_repo
        self.session_repo = session_repo
        self.token_repo = token_repo
        self.audit_repo = audit_repo
        self.oauth_repo = oauth_repo
        self.verification_token_repo = verification_token_repo
        self.email_service = email_service
        self.background_tasks = background_tasks
        self.tenant_id = user_repo.tenant_id

    async def _check_ip_anomaly(
        self,
        user_id: uuid.UUID,
        current_ip: str | None,
        user_agent: str | None,
        fingerprint: str | None
    ) -> None:
        """Check if the current login/refresh IP is an anomaly compared to the last 5 sessions."""
        if not current_ip:
            return
            
        recent_sessions = await self.session_repo.get_recent_by_user(user_id, limit=5)
        if not recent_sessions:
            return
            
        current_country = get_country_from_ip(current_ip)
        
        # Gather countries from recent sessions
        past_countries = set()
        for sess in recent_sessions:
            if sess.ip_address and sess.ip_address != current_ip:
                past_countries.add(get_country_from_ip(sess.ip_address))
                
        # If we have past countries, and current country is not in that list
        if past_countries and current_country not in past_countries:
            await self.audit_repo.create(
                action="suspicious_login_location",
                user_id=user_id,
                ip_address=current_ip,
                user_agent=user_agent,
                device_fingerprint=fingerprint,
                metadata_json={
                    "current_country": current_country,
                    "past_countries": list(past_countries)
                }
            )
            
            # Send warning email
            user = await self.user_repo.get_by_id(user_id)
            if user:
                self.background_tasks.add_task(
                    self.email_service.send_email,
                    to_email=user.email,
                    subject="Предупреждение безопасности: обнаружен подозрительный вход - Auth Service",
                    body=f"""
                    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ef4444; border-radius: 8px;">
                        <h2 style="color: #ef4444; margin-top: 0;">Подозрительная активность входа</h2>
                        <p>Здравствуйте,</p>
                        <p>Мы обнаружили вход в ваш аккаунт из необычного местоположения:</p>
                        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                            <tr style="background: #f9fafb;">
                                <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #e5e7eb;">IP-адрес:</td>
                                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{current_ip}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #e5e7eb;">Страна:</td>
                                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{current_country}</td>
                            </tr>
                            <tr style="background: #f9fafb;">
                                <td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #e5e7eb;">Устройство:</td>
                                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{user_agent or 'Неизвестно'}</td>
                            </tr>
                        </table>
                        <p>Этот вход отличается от вашей обычной географии входа (ранее использовались: {', '.join(past_countries)}).</p>
                        <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
                        <p style="font-weight: bold;">Если это были не вы:</p>
                        <p>Пожалуйста, <strong>немедленно смените пароль вашего аккаунта</strong> и завершите все активные сеансы в личном кабинете.</p>
                    </div>
                    """
                )


    async def register_user(self, email: str, password: str, role: str = "user") -> User:
        """Register a new user in the system."""
        # 1. Check if user already exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            # Note: For production we might want to prevent email enumeration,
            # but for a register endpoint, standard behavior is returning conflict.
            raise ValueError("Email already registered")

        # 2. Hash password and create user
        pwd_hash = await hash_password(password)
        user = await self.user_repo.create(
            email=email,
            password_hash=pwd_hash,
            role=role,
            is_verified=False # Requires verification link (Phase 2)
        )

        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
        raw_token = await self.verification_token_repo.create_token(
            user_id=user.id,
            token_type='email_verify',
            expires_at=expiry
        )

        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
        self.background_tasks.add_task(
            self.email_service.send_verification_email,
            email=user.email,
            verification_link=verify_url
        )

        # 3. Write Audit Log
        await self.audit_repo.create(
            action="user_registered",
            user_id=user.id,
            metadata_json={"email": email.lower().strip(), "role": role}
        )

        return user

    async def login_user(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        accept_language: str | None = None
    ) -> LoginResult:
        """Authenticate user and issue new session and tokens."""
        # Calculate fingerprint
        fingerprint = calculate_device_fingerprint(user_agent, ip_address, accept_language)

        # 1. Fetch user
        user = await self.user_repo.get_by_email(email)
        if not user or not user.password_hash or not await verify_password(password, user.password_hash):
            LOGIN_COUNTER.labels(status="failed", tenant_id=str(self.tenant_id)).inc()
            await self.audit_repo.create(
                action="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=fingerprint,
                metadata_json={"email": email.lower().strip(), "reason": "invalid_credentials"}
            )
            raise ValueError("Invalid email or password")

        # 2. Verify active status
        if not user.is_active:
            LOGIN_COUNTER.labels(status="failed", tenant_id=str(self.tenant_id)).inc()
            await self.audit_repo.create(
                action="login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=fingerprint,
                metadata_json={"reason": "account_deactivated"}
            )
            raise ValueError("Account is deactivated")

        # Check if 2FA is enabled
        if user.is_two_factor_enabled:
            mfa_token = create_mfa_token(user.id, self.tenant_id)
            await self.audit_repo.create(
                action="2fa_challenge_issued",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=fingerprint
            )
            return LoginResult(requires_2fa=True, mfa_token=mfa_token)

        # Check for location anomaly (mock GeoIP)
        await self._check_ip_anomaly(user.id, ip_address, user_agent, fingerprint)

        # 3. Create Session
        session_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = await self.session_repo.create(
            user_id=user.id,
            expires_at=session_expiry,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint
        )

        # 4. Generate & Store Refresh Token (SHA-256 hashed)
        raw_refresh = generate_opaque_token()
        refresh_hash = hash_opaque_token(raw_refresh)
        family_id = str(uuid.uuid4())
        
        await self.token_repo.create(
            session_id=session.id,
            token_hash=refresh_hash,
            family_id=family_id,
            expires_at=session_expiry
        )

        # 5. Generate Access Token (JWT)
        access_token = create_access_token(
            subject=user.id,
            tenant_id=self.tenant_id,
            role=user.role,
            session_id=session.id
        )

        # 6. Audit Log
        LOGIN_COUNTER.labels(status="success", tenant_id=str(self.tenant_id)).inc()
        ACTIVE_SESSIONS.labels(tenant_id=str(self.tenant_id)).inc()
        await self.audit_repo.create(
            action="login_success",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint,
            metadata_json={"session_id": str(session.id)}
        )

        return LoginResult(
            requires_2fa=False,
            access_token=access_token,
            refresh_token=raw_refresh,
            session=session
        )

    async def complete_2fa_login(
        self,
        mfa_token: str,
        totp_code: str,
        two_factor_service: any,
        ip_address: str | None = None,
        user_agent: str | None = None,
        accept_language: str | None = None
    ) -> LoginResult:
        """Verify the MFA token and the TOTP/backup code, then issue a session and tokens."""
        # Calculate fingerprint
        fingerprint = calculate_device_fingerprint(user_agent, ip_address, accept_language)

        # 1. Verify MFA token
        payload = verify_mfa_token(mfa_token)
        if not payload or str(payload.get("tenant_id")) != str(self.tenant_id):
            raise ValueError("Invalid or expired 2FA token")
            
        user_id = uuid.UUID(payload["sub"])
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or deactivated")
            
        # 2. Verify TOTP / backup code
        is_verified = await two_factor_service.verify_2fa(user, totp_code)
        
        if not is_verified:
            LOGIN_COUNTER.labels(status="failed", tenant_id=str(self.tenant_id)).inc()
            await self.audit_repo.create(
                action="login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=fingerprint,
                metadata_json={"reason": "invalid_2fa_code"}
            )
            raise ValueError("Invalid 2FA code")
            
        # Check for location anomaly (mock GeoIP)
        await self._check_ip_anomaly(user.id, ip_address, user_agent, fingerprint)

        # 3. Create Session
        session_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = await self.session_repo.create(
            user_id=user.id,
            expires_at=session_expiry,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint
        )

        # 4. Generate & Store Refresh Token (SHA-256 hashed)
        raw_refresh = generate_opaque_token()
        refresh_hash = hash_opaque_token(raw_refresh)
        family_id = str(uuid.uuid4())
        
        await self.token_repo.create(
            session_id=session.id,
            token_hash=refresh_hash,
            family_id=family_id,
            expires_at=session_expiry
        )

        # 5. Generate Access Token (JWT)
        access_token = create_access_token(
            subject=user.id,
            tenant_id=self.tenant_id,
            role=user.role,
            session_id=session.id
        )

        # 6. Audit Log
        LOGIN_COUNTER.labels(status="success", tenant_id=str(self.tenant_id)).inc()
        ACTIVE_SESSIONS.labels(tenant_id=str(self.tenant_id)).inc()
        await self.audit_repo.create(
            action="login_success",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint,
            metadata_json={"session_id": str(session.id), "mfa_verified": True}
        )

        return LoginResult(
            requires_2fa=False,
            access_token=access_token,
            refresh_token=raw_refresh,
            session=session
        )

    async def refresh_tokens(
        self,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        accept_language: str | None = None
    ) -> tuple[str, str]:
        """Rotate Refresh Token and issue new Access Token."""
        fingerprint = calculate_device_fingerprint(user_agent, ip_address, accept_language)
        token_hash = hash_opaque_token(raw_refresh_token)

        # 1. Look up refresh token
        token = await self.token_repo.get_by_hash(token_hash)
        if not token:
            REFRESH_COUNTER.labels(status="failed").inc()
            await self.audit_repo.create(
                action="refresh_token_not_found",
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=fingerprint
            )
            raise ValueError("Invalid refresh token")

        # Get session details
        session = await self.session_repo.get_by_id(token.session_id)
        if not session:
            raise ValueError("Session not found")

        # 2. Check for Reuse Attack (STRICT SECURITY)
        if token.is_revoked:
            # REUSE ATTACK DETECTED!
            REFRESH_COUNTER.labels(status="reuse_detected").inc()
            if not session.is_revoked:
                ACTIVE_SESSIONS.labels(tenant_id=str(self.tenant_id)).dec()
            # Revoke all tokens in family
            await self.token_repo.revoke_family(token.family_id)
            # Revoke current session
            await self.session_repo.revoke(session.id)
            
            # Log critical security audit event
            await self.audit_repo.create(
                action="refresh_reuse_attack",
                user_id=session.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=fingerprint,
                metadata_json={
                    "session_id": str(session.id),
                    "family_id": token.family_id,
                    "attempted_token_id": str(token.id)
                }
            )
            # Commit immediately to persist the security revocation to DB,
            # since raising ValueError will trigger rollback in DB session context manager
            await self.session_repo.db.commit()
            
            raise ValueError("Session revoked due to token reuse detection")

        # 3. Check expiration
        if token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            REFRESH_COUNTER.labels(status="failed").inc()
            raise ValueError("Refresh token expired")
 
        # 4. Check if session is revoked
        if session.is_revoked or session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            REFRESH_COUNTER.labels(status="failed").inc()
            raise ValueError("Session is expired or revoked")

        # Check for location anomaly (mock GeoIP)
        await self._check_ip_anomaly(session.user_id, ip_address, user_agent, fingerprint)

        # 5. Revoke current token (Mark as used)
        token.is_revoked = True
        await self.token_repo.revoke(token.id)

        # 6. Issue new Refresh Token (Same family)
        new_raw_refresh = generate_opaque_token()
        new_refresh_hash = hash_opaque_token(new_raw_refresh)
        
        await self.token_repo.create(
            session_id=session.id,
            token_hash=new_refresh_hash,
            family_id=token.family_id,
            expires_at=token.expires_at # Keep same expiry as original token/session
        )

        # 7. Fetch user to retrieve current role
        user = await self.user_repo.get_by_id(session.user_id)
        if not user or not user.is_active:
            raise ValueError("User is inactive or not found")

        # 8. Issue new Access Token (JWT)
        new_access_token = create_access_token(
            subject=user.id,
            tenant_id=self.tenant_id,
            role=user.role,
            session_id=session.id
        )

        # 9. Audit Log
        REFRESH_COUNTER.labels(status="success").inc()
        await self.audit_repo.create(
            action="token_refreshed",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint,
            metadata_json={"session_id": str(session.id)}
        )

        return new_access_token, new_raw_refresh

    async def logout_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Revoke session and all associated refresh tokens."""
        session = await self.session_repo.get_by_id(session_id)
        if not session or session.user_id != user_id:
            return False

        # Revoke session
        if not session.is_revoked:
            ACTIVE_SESSIONS.labels(tenant_id=str(self.tenant_id)).dec()
        await self.session_repo.revoke(session.id)

        # Revoke tokens associated with session
        # We can just revoke by setting is_revoked for family
        # (Though technically it's safer to revoke family_id)
        # Find any active token for this session to get family_id
        # For simplicity, we just revoke all tokens linked to this session.
        # But wait! A session can have multiple tokens if rotated.
        # We can write a quick update statement in database.
        # Since we have session.id, let's revoke all refresh tokens for this session.
        # Let's add a helper to token_repo if needed or do it here.
        # Actually, TokenRepository.revoke_family works by family_id.
        # But we can also query the database or update.
        # Let's just find the token(s) and revoke them.
        # In our implementation of TokenRepository, we have access to db.
        from sqlalchemy import update
        from src.models.token import RefreshToken
        await self.token_repo.db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == session.id)
            .values(is_revoked=True)
        )

        await self.audit_repo.create(
            action="user_logged_out",
            user_id=user_id,
            metadata_json={"session_id": str(session.id)}
        )
        return True

    async def logout_all_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke all sessions and tokens for user."""
        # Revoke all sessions
        revoked_count = await self.session_repo.revoke_all_by_user(user_id)
        if revoked_count > 0:
            ACTIVE_SESSIONS.labels(tenant_id=str(self.tenant_id)).dec(revoked_count)
        
        # Revoke all refresh tokens for these sessions
        from sqlalchemy import update, select
        from src.models.token import RefreshToken
        from src.models.session import Session
        await self.token_repo.db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id.in_(
                select(Session.id).where(Session.user_id == user_id)
            ))
            .values(is_revoked=True)
        )

        await self.audit_repo.create(
            action="user_logged_out_all_devices",
            user_id=user_id
        )
        return revoked_count

    async def request_email_verification(self, user_id: uuid.UUID) -> None:
        """Generate verification token, store in repository, and email the link to the user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if user.is_verified:
            return
            
        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
        
        raw_token = await self.verification_token_repo.create_token(
            user_id=user.id,
            token_type='email_verify',
            expires_at=expiry
        )
        
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
        self.background_tasks.add_task(
            self.email_service.send_verification_email,
            email=user.email,
            verification_link=verify_url
        )

    async def verify_email(self, token: str) -> None:
        """Verify user's email using token from repository."""
        v_token = await self.verification_token_repo.get_valid_token(token, token_type='email_verify')
        if not v_token:
            raise ValueError("Invalid or expired verification token")
            
        if v_token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            await self.verification_token_repo.delete_token(v_token.id)
            raise ValueError("Verification token has expired")
            
        user = await self.user_repo.get_by_id(v_token.user_id)
        if not user:
            raise ValueError("User not found")
            
        user.is_verified = True
        await self.user_repo.update(user)
        
        # Delete token after successful use
        await self.verification_token_repo.delete_token(v_token.id)
        
        await self.audit_repo.create(
            action="email_verified",
            user_id=user.id
        )

    async def request_password_reset(self, email: str) -> None:
        """Request a password reset link. Prevents email enumeration."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            logger.warning(f"Password reset requested for non-existent email {email}")
            return
            
        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        
        raw_token = await self.verification_token_repo.create_token(
            user_id=user.id,
            token_type='password_reset',
            expires_at=expiry
        )
        
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        self.background_tasks.add_task(
            self.email_service.send_password_reset_email,
            email=user.email,
            reset_link=reset_url
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        """Reset user's password, invalidating all current sessions."""
        v_token = await self.verification_token_repo.get_valid_token(token, token_type='password_reset')
        if not v_token:
            raise ValueError("Invalid or expired password reset token")
            
        if v_token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            await self.verification_token_repo.delete_token(v_token.id)
            raise ValueError("Password reset token has expired")
            
        user = await self.user_repo.get_by_id(v_token.user_id)
        if not user:
            raise ValueError("User not found")
            
        # Update password hash
        user.password_hash = await hash_password(new_password)
        await self.user_repo.update(user)
        
        # Security Best Practice: Revoke all sessions on password change
        await self.logout_all_sessions(user.id)
        
        # Delete token after successful use
        await self.verification_token_repo.delete_token(v_token.id)
        
        await self.audit_repo.create(
            action="password_reset_success",
            user_id=user.id
        )

    async def get_user_audit_logs(self, user_id: uuid.UUID, limit: int = 50) -> list:
        """Fetch recent audit logs for a specific user."""
        from sqlalchemy import select, desc
        from src.models.audit import AuditLog
        
        result = await self.audit_repo.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def revoke_specific_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
        """Revoke a specific session and its tokens, if it belongs to the user."""
        session = await self.session_repo.get_by_id(session_id)
        if not session or session.user_id != user_id:
            return False

        if not session.is_revoked:
            ACTIVE_SESSIONS.labels(tenant_id=str(self.tenant_id)).dec()
            
        await self.session_repo.revoke(session.id)

        from sqlalchemy import update
        from src.models.token import RefreshToken
        await self.token_repo.db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == session.id)
            .values(is_revoked=True)
        )

        await self.audit_repo.create(
            action="specific_session_revoked",
            user_id=user_id,
            metadata_json={"revoked_session_id": str(session.id)}
        )
        return True
