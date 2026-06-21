import uuid
import hashlib
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import Request, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import settings
from src.database import get_db
from src.core.context import set_tenant_id, get_tenant_id
from src.core.security import verify_access_token, hash_opaque_token
from src.repositories.tenant import TenantRepository
from src.repositories.user import UserRepository
from src.repositories.session import SessionRepository
from src.repositories.token import TokenRepository
from src.repositories.audit import AuditRepository
from src.repositories.oauth import OAuthRepository
from src.repositories.two_factor import TwoFactorRepository
from src.repositories.webauthn import WebAuthnRepository
from src.services.auth import AuthService
from src.services.oauth import OAuthService
from src.services.email import EmailService
from src.services.two_factor import TwoFactorService
from src.services.webauthn import WebAuthnService
from src.models.user import User

# Define header schemas
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)
tenant_id_header = APIKeyHeader(name="X-Tenant-ID", auto_error=False)

async def _resolve_from_token(request: Request) -> uuid.UUID | None:
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    if token:
        payload = verify_access_token(token)
        if payload and "tenant_id" in payload:
            try:
                return uuid.UUID(payload["tenant_id"])
            except ValueError:
                pass
    return None

async def _resolve_from_refresh_token(request: Request, db: AsyncSession) -> uuid.UUID | None:
    if request.url.path.endswith("/refresh"):
        refresh_token = request.cookies.get("refresh_token") or request.headers.get("X-Refresh-Token")
        if refresh_token:
            token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
            from src.models.token import RefreshToken
            from src.models.session import Session
            from src.models.user import User as DBUser
            from sqlalchemy import select
            result = await db.execute(
                select(DBUser.tenant_id)
                .join(Session, Session.user_id == DBUser.id)
                .join(RefreshToken, RefreshToken.session_id == Session.id)
                .where(RefreshToken.token_hash == token_hash)
            )
            return result.scalar_one_or_none()
    return None

async def _resolve_from_api_key(db: AsyncSession, x_api_key: str | None) -> uuid.UUID | None:
    if x_api_key:
        api_key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
        tenant_repo = TenantRepository(db)
        tenant = await tenant_repo.get_by_api_key_hash(api_key_hash)
        if tenant:
            return tenant.id
    return None

async def _resolve_from_tenant_id_header_or_param(db: AsyncSession, x_tenant_id: str | None, tenant_param: str | None) -> uuid.UUID | None:
    tenant_val = x_tenant_id or tenant_param
    if tenant_val:
        try:
            tenant_uuid = uuid.UUID(tenant_val)
            tenant_repo = TenantRepository(db)
            tenant = await tenant_repo.get_by_id(tenant_uuid)
            if tenant:
                return tenant.id
        except ValueError:
            pass
    return None

async def _resolve_from_verification_token(request: Request, db: AsyncSession) -> uuid.UUID | None:
    token_param = request.query_params.get("token")
    if token_param:
        try:
            from src.models.token import VerificationToken
            from src.models.user import User as DBUser
            from sqlalchemy import select
            
            res = await db.execute(
                select(DBUser)
                .join(VerificationToken, VerificationToken.user_id == DBUser.id)
                .where(VerificationToken.token == token_param)
            )
            db_user = res.scalar_one_or_none()
            if db_user:
                return db_user.tenant_id
        except Exception:
            pass

    if request.method == "POST" and request.url.path.endswith("/reset-password"):
        try:
            body_json = await request.json()
            token_body = body_json.get("token")
            if token_body:
                from src.models.token import VerificationToken
                from src.models.user import User as DBUser
                from sqlalchemy import select
                
                res = await db.execute(
                    select(DBUser)
                    .join(VerificationToken, VerificationToken.user_id == DBUser.id)
                    .where(VerificationToken.token == token_body)
                )
                db_user = res.scalar_one_or_none()
                if db_user:
                    return db_user.tenant_id
        except Exception:
            pass
    return None

async def _resolve_from_mfa_token(request: Request) -> uuid.UUID | None:
    if request.method == "POST" and request.url.path.endswith("/2fa/verify"):
        try:
            body_json = await request.json()
            mfa_token_body = body_json.get("mfa_token")
            if mfa_token_body:
                from src.core.security import verify_mfa_token
                payload = verify_mfa_token(mfa_token_body)
                if payload and "tenant_id" in payload:
                    return uuid.UUID(payload["tenant_id"])
        except Exception:
            pass
    return None

async def _resolve_from_oauth_state(request: Request) -> uuid.UUID | None:
    if request.query_params.get("state") and "/oauth/" in request.url.path and "/callback" in request.url.path:
        try:
            state_param = request.query_params.get("state")
            from src.core.redis import init_redis
            import json
            redis_client = await init_redis()
            state_data_json = await redis_client.get(f"oauth_state:{state_param}")
            if state_data_json:
                state_data = json.loads(state_data_json)
                return uuid.UUID(state_data["tenant_id"])
        except Exception:
            pass
    return None

async def resolve_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Depends(api_key_header),
    x_tenant_id: str | None = Depends(tenant_id_header)
) -> uuid.UUID:
    """
    FastAPI dependency to resolve the tenant from either:
    1. JWT Access Token (for authenticated routes)
    2. JWT Refresh Token (for /refresh endpoint)
    3. X-Api-Key header (hashed lookup in DB)
    4. X-Tenant-ID header or ?tenant_id= query param
    5. Verification token (reset password, verify email)
    6. MFA token (/2fa/verify)
    7. OAuth state (/oauth/.../callback)
    """
    tenant_param = request.query_params.get("tenant_id")
    
    resolvers = [
        lambda: _resolve_from_token(request),
        lambda: _resolve_from_refresh_token(request, db),
        lambda: _resolve_from_api_key(db, x_api_key),
        lambda: _resolve_from_tenant_id_header_or_param(db, x_tenant_id, tenant_param),
        lambda: _resolve_from_verification_token(request, db),
        lambda: _resolve_from_mfa_token(request),
        lambda: _resolve_from_oauth_state(request),
    ]
    
    for resolver in resolvers:
        tenant_id = await resolver()
        if tenant_id:
            set_tenant_id(tenant_id)
            return tenant_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not resolve tenant context. Provide X-Api-Key, X-Tenant-ID or a valid token."
    )


# Instantiations of Scoped Repositories
async def get_user_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> UserRepository:
    return UserRepository(db, tenant_id)

async def get_session_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> SessionRepository:
    return SessionRepository(db, tenant_id)

async def get_token_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> TokenRepository:
    return TokenRepository(db, tenant_id)

async def get_audit_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> AuditRepository:
    return AuditRepository(db, tenant_id)

async def get_oauth_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> OAuthRepository:
    return OAuthRepository(db, tenant_id)

async def get_two_factor_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> TwoFactorRepository:
    return TwoFactorRepository(db, tenant_id)

async def get_email_service() -> EmailService:
    return EmailService()

async def get_two_factor_service(
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(get_user_repository),
    two_factor_repo: TwoFactorRepository = Depends(get_two_factor_repository),
    email_service: EmailService = Depends(get_email_service)
) -> TwoFactorService:
    return TwoFactorService(user_repo, two_factor_repo, email_service, background_tasks)

from fastapi import BackgroundTasks
from src.repositories.token import TokenRepository, VerificationTokenRepository

async def get_verification_token_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> VerificationTokenRepository:
    return VerificationTokenRepository(db, tenant_id)

from src.services.captcha import CaptchaService

def get_captcha_service() -> CaptchaService:
    return CaptchaService()

async def get_auth_service(
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    token_repo: TokenRepository = Depends(get_token_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    oauth_repo: OAuthRepository = Depends(get_oauth_repository),
    verification_token_repo: VerificationTokenRepository = Depends(get_verification_token_repository),
    email_service: EmailService = Depends(get_email_service)
) -> AuthService:
    return AuthService(
        user_repo, session_repo, token_repo, audit_repo, oauth_repo, 
        verification_token_repo, email_service, background_tasks
    )

async def get_oauth_service_dep(
    oauth_repo: OAuthRepository = Depends(get_oauth_repository)
) -> OAuthService:
    return OAuthService(oauth_repo)

async def get_tenant_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> TenantRepository:
    return TenantRepository(db, tenant_id)

from src.services.tenant import TenantService

async def get_tenant_service(
    background_tasks: BackgroundTasks,
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    email_service: EmailService = Depends(get_email_service)
) -> TenantService:
    return TenantService(tenant_repo, audit_repo, email_service, background_tasks)

async def get_webauthn_repository(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
) -> WebAuthnRepository:
    return WebAuthnRepository(db, tenant_id)

async def get_webauthn_service(
    user_repo: UserRepository = Depends(get_user_repository),
    webauthn_repo: WebAuthnRepository = Depends(get_webauthn_repository),
    auth_service: AuthService = Depends(get_auth_service)
) -> WebAuthnService:
    return WebAuthnService(user_repo, webauthn_repo, auth_service)

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """Dependency to retrieve the authenticated user from Access Token (Cookie or Bearer)."""
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
        
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )
        
    user_id_str = payload.get("sub")
    session_id_str = payload.get("session_id")
    
    if not user_id_str or not session_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
        
    try:
        user_uuid = uuid.UUID(user_id_str)
        session_uuid = uuid.UUID(session_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token identifier formats"
        )
        
    # Check Redis for session validity and cached user to save DB query
    from src.core.redis import init_redis
    import json
    redis_client = await init_redis()
    cache_key = f"session_user:{session_uuid}"
    cached_data = await redis_client.get(cache_key)
    
    if cached_data:
        user_data = json.loads(cached_data)
        user = User(id=uuid.UUID(user_data["id"]), role=user_data["role"], is_active=user_data["is_active"], email=user_data.get("email", ""))
    else:
        # Check if session is revoked in DB
        from src.models.session import Session as DBSession
        from sqlalchemy import select
        result_session = await db.execute(
            select(DBSession).where(DBSession.id == session_uuid, DBSession.is_revoked == False)
        )
        session = result_session.scalar_one_or_none()
        if not session or session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked or expired"
            )

        # Fetch user
        user = await user_repo.get_by_id(user_uuid)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated"
            )
            
        # Cache for 60 seconds
        user_data = {"id": str(user.id), "role": user.role, "is_active": user.is_active, "email": user.email}
        await redis_client.set(cache_key, json.dumps(user_data), ex=60)

    # Inject session_id into request state for endpoint handlers
    request.state.session_id = session_uuid
    
    return user


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions"
            )
        return current_user

class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission
        
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        # System admins bypass permission checks
        if current_user.role == "admin":
            return current_user
            
        from src.models.rbac import UserRole, Role, RolePermission
        from sqlalchemy import select
        
        result = await db.execute(
            select(RolePermission)
            .join(Role)
            .join(UserRole)
            .where(
                UserRole.user_id == current_user.id,
                RolePermission.permission == self.required_permission
            )
        )
        
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: missing '{self.required_permission}' permission"
            )
            
        return current_user


async def requires_fresh_auth(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency that enforces Step-up Auth (MFA freshness)."""
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization")
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    # Check token issuance time (iat)
    iat = payload.get("iat")
    if not iat:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing iat claim")
        
    # If token is older than 10 minutes, require step-up auth
    token_age_seconds = datetime.now(timezone.utc).timestamp() - iat
    if token_age_seconds > 600:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Step-up authentication required. Please re-authenticate to perform this action."
        )
        
    return current_user

