import uuid
import json
from urllib.parse import urlparse
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers.structs import (
    UserVerificationRequirement,
    AuthenticatorSelectionCriteria,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
    RegistrationCredential,
    AuthenticationCredential,
)
from src.config import settings
from src.repositories.user import UserRepository
from src.repositories.webauthn import WebAuthnRepository
from src.core.redis import init_redis
from src.services.auth import AuthService, LoginResult

class WebAuthnService:
    def __init__(
        self,
        user_repo: UserRepository,
        webauthn_repo: WebAuthnRepository,
        auth_service: AuthService
    ):
        self.user_repo = user_repo
        self.webauthn_repo = webauthn_repo
        self.auth_service = auth_service
        
        # Determine RP ID from DOMAIN config
        parsed = urlparse(settings.DOMAIN)
        self.rp_id = parsed.hostname or "localhost"
        self.rp_name = settings.APP_NAME
        self.origin = settings.DOMAIN

    async def _save_challenge(self, key: str, challenge: bytes) -> None:
        redis = await init_redis()
        # WebAuthn challenges are typically valid for a few minutes (5 mins)
        await redis.setex(f"webauthn_challenge:{key}", 300, challenge)

    async def _get_challenge(self, key: str) -> bytes | None:
        redis = await init_redis()
        challenge = await redis.get(f"webauthn_challenge:{key}")
        if challenge:
            await redis.delete(f"webauthn_challenge:{key}")
        return challenge

    async def begin_registration(self, user_id: uuid.UUID) -> dict:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Get existing credentials to exclude them
        existing_credentials = await self.webauthn_repo.get_by_user(user_id)
        exclude_credentials = [
            {"id": cred.credential_id, "type": "public-key"}
            for cred in existing_credentials
        ]

        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=str(user.id).encode("utf-8"),
            user_name=user.email,
            user_display_name=user.email,
            exclude_credentials=exclude_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM, # Passkeys are platform attachment typically
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )

        # Save challenge associated with user_id
        await self._save_challenge(f"reg_{user.id}", options.challenge)

        return json.loads(options_to_json(options))

    async def complete_registration(self, user_id: uuid.UUID, response_data: dict, credential_name: str = "Passkey") -> dict:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        expected_challenge = await self._get_challenge(f"reg_{user.id}")
        if not expected_challenge:
            raise ValueError("Challenge expired or not found")

        try:
            credential = RegistrationCredential.parse_raw(json.dumps(response_data))
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=expected_challenge,
                expected_origin=self.origin,
                expected_rp_id=self.rp_id,
                require_user_verification=True,
            )
        except Exception as e:
            raise ValueError(f"Registration failed: {str(e)}")

        # Save the new credential
        await self.webauthn_repo.create(
            user_id=user.id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            transports=None, # Extract if needed
            name=credential_name
        )

        return {"verified": True}

    async def begin_login(self, email: str) -> dict:
        user = await self.user_repo.get_by_email(email)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        # Get credentials
        existing_credentials = await self.webauthn_repo.get_by_user(user.id)
        if not existing_credentials:
            raise ValueError("No passkeys registered for this user")

        allow_credentials = [
            {"id": cred.credential_id, "type": "public-key"}
            for cred in existing_credentials
        ]

        options = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        # Save challenge associated with email
        await self._save_challenge(f"login_{user.email}", options.challenge)

        return json.loads(options_to_json(options))

    async def complete_login(
        self, 
        email: str, 
        response_data: dict,
        ip_address: str | None = None,
        user_agent: str | None = None,
        accept_language: str | None = None
    ) -> LoginResult:
        user = await self.user_repo.get_by_email(email)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        expected_challenge = await self._get_challenge(f"login_{user.email}")
        if not expected_challenge:
            raise ValueError("Challenge expired or not found")

        try:
            credential = AuthenticationCredential.parse_raw(json.dumps(response_data))
        except Exception as e:
            raise ValueError(f"Invalid credential payload: {str(e)}")

        # Find credential in DB
        db_credential = await self.webauthn_repo.get_by_credential_id(base64url_to_bytes(credential.id))
        if not db_credential or db_credential.user_id != user.id:
            raise ValueError("Credential not found")

        try:
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=expected_challenge,
                expected_origin=self.origin,
                expected_rp_id=self.rp_id,
                credential_public_key=db_credential.public_key,
                credential_current_sign_count=db_credential.sign_count,
                require_user_verification=True,
            )
        except Exception as e:
            # We must log failed login attempts via auth_service if needed, 
            # but auth_service._check_ip_anomaly is private and audit logs usually happen there.
            raise ValueError(f"Authentication failed: {str(e)}")

        # Update sign count to prevent replay attacks
        await self.webauthn_repo.update_sign_count(db_credential.id, verification.new_sign_count)

        # Bypass password check and issue tokens/session
        # We can simulate a successful login inside auth_service.
        # But auth_service.login_user checks password.
        # We need a new method in auth_service to issue tokens directly for passkey/oauth.
        # Actually OAuth uses similar logic. Let's look at how OAuth does it or implement it.
        # Wait, we can reuse auth_service._check_ip_anomaly and create a session directly.
        from src.core.fingerprint import calculate_device_fingerprint
        from src.core.security import create_access_token, generate_opaque_token, hash_opaque_token
        from datetime import datetime, timezone, timedelta

        fingerprint = calculate_device_fingerprint(user_agent, ip_address, accept_language)
        
        # Check for anomaly
        await self.auth_service._check_ip_anomaly(user.id, ip_address, user_agent, fingerprint)

        # 3. Create Session
        session_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = await self.auth_service.session_repo.create(
            user_id=user.id,
            expires_at=session_expiry,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint
        )

        # 4. Generate & Store Refresh Token
        raw_refresh = generate_opaque_token()
        refresh_hash = hash_opaque_token(raw_refresh)
        family_id = str(uuid.uuid4())
        
        await self.auth_service.token_repo.create(
            session_id=session.id,
            token_hash=refresh_hash,
            family_id=family_id,
            expires_at=session_expiry
        )

        # 5. Generate Access Token (JWT)
        access_token = create_access_token(
            subject=user.id,
            tenant_id=self.auth_service.tenant_id,
            role=user.role,
            session_id=session.id
        )

        # 6. Audit Log
        from src.core.metrics import LOGIN_COUNTER, ACTIVE_SESSIONS
        LOGIN_COUNTER.labels(status="success", tenant_id=str(self.auth_service.tenant_id)).inc()
        ACTIVE_SESSIONS.labels(tenant_id=str(self.auth_service.tenant_id)).inc()
        await self.auth_service.audit_repo.create(
            action="login_success",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=fingerprint,
            metadata_json={"session_id": str(session.id), "method": "passkey"}
        )

        return LoginResult(
            requires_2fa=False, # Passkey is inherently 2FA (possession + inherence)
            access_token=access_token,
            refresh_token=raw_refresh,
            session=session
        )
