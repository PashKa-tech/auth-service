import uuid
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from src.api.deps import (
    get_auth_service,
    get_current_user,
    resolve_tenant,
    get_captcha_service
)
from src.services.auth import AuthService
from src.services.captcha import CaptchaService
from src.models.user import User
from src.core.rate_limit import is_rate_limited, RateLimiter
from src.schemas.common import UnifiedResponse
from src.schemas.auth import UserRegisterRequest, UserLoginRequest
from src.api.v1.auth_utils import get_client_ip, is_mobile_client, set_auth_cookies, clear_auth_cookies, handle_auth_success_response
from src.config import settings

router = APIRouter()

@router.post("/register", response_model=UnifiedResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RateLimiter("register_ip", 5))])
async def register(
    request: Request,
    body: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    captcha_service: CaptchaService = Depends(get_captcha_service)
):
    await captcha_service.verify_captcha(body.captcha_token, body.captcha_id, get_client_ip(request))
    global_limit_key = f"tenant_rpm:{tenant_id}"
    
    if await is_rate_limited(global_limit_key, 1000):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Tenant rate limit exceeded")

    from src.core.security import check_pwned_password
    if await check_pwned_password(body.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password has appeared in a data breach. Please choose a different password.")

    try:
        user = await auth_service.register_user(body.email, body.password)
        return UnifiedResponse(
            success=True,
            data={"id": str(user.id), "email": user.email, "role": user.role}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.post("/login", response_model=UnifiedResponse, dependencies=[Depends(RateLimiter("login_ip", 5))])
async def login(
    request: Request,
    response: Response,
    body: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    captcha_service: CaptchaService = Depends(get_captcha_service)
):
    await captcha_service.verify_captcha(body.captcha_token, body.captcha_id, get_client_ip(request))
    global_limit_key = f"tenant_rpm:{tenant_id}"
    
    if await is_rate_limited(global_limit_key, 1000):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Tenant rate limit exceeded")

    try:
        ip = get_client_ip(request)
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        
        login_result = await auth_service.login_user(
            email=body.email,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
            accept_language=lang
        )

        if login_result.requires_2fa:
            return UnifiedResponse(
                success=True,
                data={
                    "requires_2fa": True,
                    "mfa_token": login_result.mfa_token
                }
            )

        access_token = login_result.access_token
        refresh_token = login_result.refresh_token
        session = login_result.session

        return handle_auth_success_response(
            request=request,
            response=response,
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=str(session.user_id),
            role="user",
            message="Login successful"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.post("/refresh", response_model=UnifiedResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    mobile = is_mobile_client(request)
    refresh_token = request.cookies.get("refresh_token")
    if mobile:
        refresh_token = request.headers.get("X-Refresh-Token") or refresh_token

    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        ip = get_client_ip(request)
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        
        import hashlib
        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        refresh_limit_key = f"refresh_limit:{tenant_id}:{token_hash}"
        if await is_rate_limited(refresh_limit_key, 10):
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
async def me(current_user: User = Depends(get_current_user)) -> UnifiedResponse:
    return UnifiedResponse(
        success=True,
        data={
            "id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "is_verified": current_user.is_verified,
            "two_factor_enabled": current_user.is_two_factor_enabled,
        }
    )
