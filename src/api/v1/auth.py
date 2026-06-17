import uuid
from typing import Any
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from src.core.context import get_request_id
from src.api.deps import get_auth_service, get_current_user, resolve_tenant, get_oauth_service_dep
from src.services.auth import AuthService
from src.services.oauth import OAuthService
from src.models.user import User
from fastapi.responses import RedirectResponse
from src.core.rate_limit import is_rate_limited
from src.core.logging import logger

router = APIRouter()

# --- Schemas ---

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UnifiedResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: Any | None = None
    meta: dict = Field(default_factory=lambda: {"version": "v1", "request_id": get_request_id()})

# --- Helper Functions ---

def is_mobile_client(request: Request) -> bool:
    """Helper to detect if client is mobile/API based on header."""
    return request.headers.get("X-Client-Type") == "mobile"

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set secure httpOnly cookies for browser clients."""
    # Access Token: httpOnly, Secure (in prod), SameSite=Lax, TTL ~ 15m
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set True in Production (requires HTTPS)
        samesite="lax",
        max_age=15 * 60, # 15 minutes
    )
    # Refresh Token: httpOnly, Secure (in prod), SameSite=Strict, TTL ~ 7d
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Set True in Production
        samesite="strict",
        max_age=7 * 24 * 60 * 60, # 7 days
    )

def clear_auth_cookies(response: Response):
    """Clear cookies on logout."""
    response.delete_cookie("access_token", httponly=True, samesite="lax")
    response.delete_cookie("refresh_token", httponly=True, samesite="strict")

# --- Routes ---

@router.post("/register", response_model=UnifiedResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    body: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    # Rate Limit checking: Global Tenant Limit & Register Rate Limit
    global_limit_key = f"tenant_rpm:{tenant_id}"
    ip_limit_key = f"register_ip:{tenant_id}:{request.client.host if request.client else 'unknown'}"
    
    if await is_rate_limited(global_limit_key, 1000): # 1000 requests per tenant per minute
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Tenant rate limit exceeded")
    if await is_rate_limited(ip_limit_key, 5): # Max 5 registration attempts per minute per IP
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Try again later.")

    try:
        user = await auth_service.register_user(body.email, body.password)
        return UnifiedResponse(
            success=True,
            data={"id": str(user.id), "email": user.email, "role": user.role}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.post("/login", response_model=UnifiedResponse)
async def login(
    request: Request,
    response: Response,
    body: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    # Rate Limit checking: Global Tenant & Login IP
    global_limit_key = f"tenant_rpm:{tenant_id}"
    ip_limit_key = f"login_ip:{tenant_id}:{request.client.host if request.client else 'unknown'}"
    
    if await is_rate_limited(global_limit_key, 1000):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Tenant rate limit exceeded")
    if await is_rate_limited(ip_limit_key, 5): # Max 5 attempts per minute per IP (bruteforce check)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again later.")

    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        
        access_token, refresh_token, session = await auth_service.login_user(
            email=body.email,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
            accept_language=lang
        )

        mobile = is_mobile_client(request)
        if mobile:
            # Return tokens in response body
            return UnifiedResponse(
                success=True,
                data={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": {"id": str(session.user_id), "role": "user"} # Simple output
                }
            )
        else:
            # Set httpOnly cookies
            set_auth_cookies(response, access_token, refresh_token)
            return UnifiedResponse(
                success=True,
                data={"message": "Login successful"}
            )
    except ValueError as e:
        # standard credential failure: return 401
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.post("/refresh", response_model=UnifiedResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    mobile = is_mobile_client(request)
    
    # Extract refresh token
    refresh_token = request.cookies.get("refresh_token")
    if mobile:
        refresh_token = request.headers.get("X-Refresh-Token") or refresh_token

    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        
        # Check rate limits for refresh operations (prevent flood)
        # We limit by refresh token hash to avoid brute forcing raw refresh tokens
        import hashlib
        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        refresh_limit_key = f"refresh_limit:{tenant_id}:{token_hash}"
        if await is_rate_limited(refresh_limit_key, 10): # Max 10 refresh calls per minute per token
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

        new_access_token, new_refresh_token = await auth_service.refresh_tokens(
            raw_refresh_token=refresh_token,
            ip_address=ip,
            user_agent=ua,
            accept_language=lang
        )

        if mobile:
            return UnifiedResponse(
                success=True,
                data={
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token
                }
            )
        else:
            set_auth_cookies(response, new_access_token, new_refresh_token)
            return UnifiedResponse(
                success=True,
                data={"message": "Token refreshed successfully"}
            )
    except ValueError as e:
        # If reuse detection triggers, we clear cookies to force re-login
        if "revoked" in str(e).lower() or "reuse" in str(e).lower():
            if not mobile:
                clear_auth_cookies(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security alert: Session revoked due to token reuse detection"
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.post("/logout", response_model=UnifiedResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session context")
        
    await auth_service.logout_user(session_id, current_user.id)
    
    mobile = is_mobile_client(request)
    if not mobile:
        clear_auth_cookies(response)
        
    return UnifiedResponse(success=True, data={"message": "Logout successful"})

@router.post("/logout-all", response_model=UnifiedResponse)
async def logout_all(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    revoked_count = await auth_service.logout_all_sessions(current_user.id)
    
    mobile = is_mobile_client(request)
    if not mobile:
        clear_auth_cookies(response)
        
    return UnifiedResponse(
        success=True,
        data={"message": f"Successfully logged out from all devices ({revoked_count} sessions revoked)"}
    )

@router.get("/me", response_model=UnifiedResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UnifiedResponse(
        success=True,
        data={
            "id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "is_verified": current_user.is_verified,
        }
    )

@router.get("/sessions", response_model=UnifiedResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    sessions = await auth_service.session_repo.list_active_by_user(current_user.id)
    data = [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() + "Z",
            "expires_at": s.expires_at.isoformat() + "Z"
        }
        for s in sessions
    ]
    return UnifiedResponse(success=True, data=data)

# --- OAuth Routes ---

@router.get("/oauth/{provider}")
async def oauth_login(
    provider: str,
    state: str | None = None,
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """Initiate OAuth flow by redirecting client to provider authorize page."""
    # If no state, generate random uuid
    oauth_state = state or str(uuid.uuid4())
    try:
        auth_url = oauth_service.get_authorization_url(provider, oauth_state)
        return RedirectResponse(url=auth_url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str | None = None,
    request: Request = None,
    response: Response = None,
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """Handle OAuth provider callback, resolve user and issue session/tokens."""
    try:
        # 1. Fetch profile information from Google/GitHub
        user_info = await oauth_service.get_user_info_from_provider(provider, code)
        
        # 2. Resolve account (linking strategy)
        user = await oauth_service.resolve_oauth_user(
            provider=provider,
            provider_user_id=user_info["provider_user_id"],
            email=user_info["email"],
            auth_service=auth_service
        )
        
        # 3. Authenticate user by creating Session (mimics AuthService.login_user)
        # Create session
        from datetime import datetime, timedelta
        from src.core.security import create_access_token, generate_opaque_token, hash_opaque_token
        from src.core.fingerprint import calculate_device_fingerprint
        
        ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        fingerprint = calculate_device_fingerprint(ua, ip, lang)
        
        session_expiry = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = await auth_service.session_repo.create(
            user_id=user.id,
            expires_at=session_expiry,
            ip_address=ip,
            user_agent=ua,
            device_fingerprint=fingerprint
        )
        
        # Create Refresh Token
        raw_refresh = generate_opaque_token()
        refresh_hash = hash_opaque_token(raw_refresh)
        family_id = str(uuid.uuid4())
        
        await auth_service.token_repo.create(
            session_id=session.id,
            token_hash=refresh_hash,
            family_id=family_id,
            expires_at=session_expiry
        )
        
        # Create Access Token
        access_token = create_access_token(
            subject=user.id,
            tenant_id=tenant_id,
            role=user.role,
            session_id=session.id
        )
        
        await auth_service.audit_repo.create(
            action="login_success",
            user_id=user.id,
            ip_address=ip,
            user_agent=ua,
            device_fingerprint=fingerprint,
            metadata_json={"session_id": str(session.id), "method": f"oauth_{provider}"}
        )

        mobile = is_mobile_client(request)
        if mobile:
            # For mobile, we return the tokens directly or redirect to a custom app scheme.
            # In our system contract, we can return a JSON with tokens
            return UnifiedResponse(
                success=True,
                data={
                    "access_token": access_token,
                    "refresh_token": raw_refresh,
                    "user": {"id": str(user.id), "role": user.role}
                }
            )
        else:
            # Set cookies and redirect back to client frontend
            # We can read the client redirect URI from state if it starts with http
            redirect_url = "http://localhost:3000" # Default fallback
            if state and (state.startswith("http://") or state.startswith("https://")):
                # Basic validation: ensure we only redirect to safe URLs
                # For MVP we allow anything, in prod we would restrict to whitelisted domains
                redirect_url = state
                
            set_auth_cookies(response, access_token, raw_refresh)
            return RedirectResponse(url=redirect_url)

    except ValueError as e:
        logger.error(f"OAuth callback resolution failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/me/linked-accounts", response_model=UnifiedResponse)
async def list_linked_accounts(
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service_dep)
):
    """List all OAuth accounts linked to the current user."""
    accounts = await oauth_service.oauth_repo.list_by_user(current_user.id)
    data = [
        {
            "id": str(acc.id),
            "provider": acc.provider,
            "provider_email": acc.provider_email,
            "linked_at": acc.linked_at.isoformat() + "Z"
        }
        for acc in accounts
    ]
    return UnifiedResponse(success=True, data=data)

@router.delete("/me/linked-accounts/{provider}", response_model=UnifiedResponse)
async def unlink_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Unlink an OAuth account from the current user."""
    # Security Guard: A user can only unlink an account if they have another login method
    # (either a password hash set OR at least one other OAuth account)
    has_password = current_user.password_hash is not None
    linked_accounts = await oauth_service.oauth_repo.list_by_user(current_user.id)
    
    other_oauth_exists = len([a for a in linked_accounts if a.provider != provider]) > 0
    
    if not has_password and not other_oauth_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink the only login method. Set a password first."
        )
        
    deleted = await oauth_service.oauth_repo.delete_by_provider(current_user.id, provider)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked account not found")
        
    await auth_service.audit_repo.create(
        action="account_unlinked",
        user_id=current_user.id,
        metadata_json={"provider": provider}
    )
    
    return UnifiedResponse(success=True, data={"message": f"Successfully unlinked {provider} account"})
