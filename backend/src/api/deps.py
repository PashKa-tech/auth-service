import uuid
import hashlib
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import Request, Depends, HTTPException, status
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
from src.services.auth import AuthService
from src.services.oauth import OAuthService
from src.services.email import EmailService
from src.services.two_factor import TwoFactorService
from src.models.user import User

# Define header schemas
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)
tenant_id_header = APIKeyHeader(name="X-Tenant-ID", auto_error=False)

async def resolve_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Depends(api_key_header),
    x_tenant_id: str | None = Depends(tenant_id_header)
) -> uuid.UUID:
    """
    FastAPI dependency to resolve the tenant from either:
    1. X-Api-Key header (hashed lookup in DB)
    2. X-Tenant-ID header (direct lookup - helpful for testing/internal calls)
    3. JWT Access Token (for authenticated routes)
    4. JWT Refresh Token (for /refresh endpoint)
    """
    tenant_id: uuid.UUID | None = None
    
    # 1. Check if it's an authenticated route via cookie/header
    # Try to extract from Access Token in cookies
    token = request.cookies.get("access_token")
    # Or try Authorization Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    if token:
        payload = verify_access_token(token)
        if payload and "tenant_id" in payload:
            try:
                tenant_id = uuid.UUID(payload["tenant_id"])
            except ValueError:
                pass

    # 2. Check for Refresh Token (only for /refresh endpoint)
    if not tenant_id and request.url.path.endswith("/refresh"):
        # For mobile/API client, refresh token might be in header X-Refresh-Token
        # For browser client, it will be in refresh_token cookie
        refresh_token = request.cookies.get("refresh_token") or request.headers.get("X-Refresh-Token")
        if refresh_token:
            token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
            # Query db for refresh token
            # Since we don't have tenant_id yet, we lookup globally first (this is safe as hash is UNIQUE)
            from src.models.token import RefreshToken
            from src.models.session import Session
            from src.models.user import User as DBUser
            from sqlalchemy import select
            result = await db.execute(
                select(RefreshToken)
                .join(Session, RefreshToken.session_id == Session.id)
                .join(DBUser, Session.user_id == DBUser.id)
                .where(RefreshToken.token_hash == token_hash)
            )
            db_token = result.scalar_one_or_none()
            if db_token:
                # We can't access user via relationship because it's lazy-loaded by default in async,
                # but we joined DBUser, so let's get it by query or fetch user_id's tenant
                result_user = await db.execute(
                    select(DBUser).where(DBUser.id == Session.user_id).join(Session).where(Session.id == db_token.session_id)
                )
                db_user = result_user.scalar_one_or_none()
                if db_user:
                    tenant_id = db_user.tenant_id

    # 3. Check X-Api-Key header
    if not tenant_id and x_api_key:
        api_key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
        tenant_repo = TenantRepository(db)
        tenant = await tenant_repo.get_by_api_key_hash(api_key_hash)
        if tenant:
            tenant_id = tenant.id

    # 4. Check X-Tenant-ID header (mainly for testing/local dev)
    if not tenant_id and x_tenant_id:
        try:
            tenant_uuid = uuid.UUID(x_tenant_id)
            tenant_repo = TenantRepository(db)
            tenant = await tenant_repo.get_by_id(tenant_uuid)
            if tenant:
                tenant_id = tenant.id
        except ValueError:
            pass

    # 5. Check query parameters (for verification or reset URLs)
    tenant_param = request.query_params.get("tenant_id")
    if not tenant_id and tenant_param:
        try:
            tenant_uuid = uuid.UUID(tenant_param)
            tenant_repo = TenantRepository(db)
            tenant = await tenant_repo.get_by_id(tenant_uuid)
            if tenant:
                tenant_id = tenant.id
        except ValueError:
            pass

    # 6. Check for Token in Query Params or POST Body (fallback for email verification or password reset)
    token_param = request.query_params.get("token")
    if not tenant_id and token_param:
        from src.core.redis import init_redis
        try:
            redis_client = await init_redis()
            val = await redis_client.get(f"email_verify:{token_param}")
            if not val:
                val = await redis_client.get(f"password_reset:{token_param}")
            
            if val:
                val_str = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                user_uuid = uuid.UUID(val_str)
                from src.models.user import User as DBUser
                from sqlalchemy import select
                res = await db.execute(select(DBUser).where(DBUser.id == user_uuid))
                db_user = res.scalar_one_or_none()
                if db_user:
                    tenant_id = db_user.tenant_id
        except Exception:
            pass

    if not tenant_id and request.method == "POST" and request.url.path.endswith("/reset-password"):
        try:
            body_json = await request.json()
            token_body = body_json.get("token")
            if token_body:
                from src.core.redis import init_redis
                redis_client = await init_redis()
                val = await redis_client.get(f"password_reset:{token_body}")
                if val:
                    val_str = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    user_uuid = uuid.UUID(val_str)
                    from src.models.user import User as DBUser
                    from sqlalchemy import select
                    res = await db.execute(select(DBUser).where(DBUser.id == user_uuid))
                    db_user = res.scalar_one_or_none()
                    if db_user:
                        tenant_id = db_user.tenant_id
        except Exception:
            pass

    if not tenant_id and request.method == "POST" and request.url.path.endswith("/2fa/verify"):
        try:
            body_json = await request.json()
            mfa_token_body = body_json.get("mfa_token")
            if mfa_token_body:
                from src.core.security import verify_mfa_token
                payload = verify_mfa_token(mfa_token_body)
                if payload and "tenant_id" in payload:
                    tenant_id = uuid.UUID(payload["tenant_id"])
        except Exception:
            pass

    if not tenant_id and request.query_params.get("state") and "/oauth/" in request.url.path and "/callback" in request.url.path:
        try:
            state_param = request.query_params.get("state")
            from src.core.redis import init_redis
            import json
            redis_client = await init_redis()
            state_data_json = await redis_client.get(f"oauth_state:{state_param}")
            if state_data_json:
                state_data = json.loads(state_data_json)
                tenant_id = uuid.UUID(state_data["tenant_id"])
        except Exception:
            pass

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not resolve tenant context. Provide X-Api-Key, X-Tenant-ID or a valid token."
        )

    # Set contextvar for structured logging and repositories
    set_tenant_id(tenant_id)
    return tenant_id


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
    user_repo: UserRepository = Depends(get_user_repository),
    two_factor_repo: TwoFactorRepository = Depends(get_two_factor_repository),
    email_service: EmailService = Depends(get_email_service)
) -> TwoFactorService:
    return TwoFactorService(user_repo, two_factor_repo, email_service)

async def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    token_repo: TokenRepository = Depends(get_token_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    oauth_repo: OAuthRepository = Depends(get_oauth_repository),
    email_service: EmailService = Depends(get_email_service)
) -> AuthService:
    return AuthService(user_repo, session_repo, token_repo, audit_repo, oauth_repo, email_service)

async def get_oauth_service_dep(
    oauth_repo: OAuthRepository = Depends(get_oauth_repository)
) -> OAuthService:
    return OAuthService(oauth_repo)

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
        
    # Check if session is revoked in DB
    # We can inject session_repo if needed or run select on Session table
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

