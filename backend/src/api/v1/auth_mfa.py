import uuid
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from src.api.deps import (
    get_auth_service,
    get_current_user,
    resolve_tenant,
    get_two_factor_service
)
from src.services.auth import AuthService
from src.services.two_factor import TwoFactorService
from src.models.user import User
from src.core.rate_limit import is_rate_limited
from src.schemas.common import UnifiedResponse
from src.schemas.auth import TwoFactorConfirmRequest, TwoFactorVerifyRequest, TwoFactorDisableRequest
from src.api.v1.auth_utils import get_client_ip, is_mobile_client

router = APIRouter()

@router.post("/2fa/setup", response_model=UnifiedResponse)
async def setup_2fa(
    request: Request,
    current_user: User = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"2fa_setup_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    user_limit_key = f"2fa_setup_user:{tenant_id}:{current_user.id}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")
    if await is_rate_limited(user_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        setup_data = await two_factor_service.setup_2fa(current_user)
        return UnifiedResponse(success=True, data=setup_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/2fa/confirm-setup", response_model=UnifiedResponse)
async def confirm_setup_2fa(
    request: Request,
    body: TwoFactorConfirmRequest,
    current_user: User = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"2fa_confirm_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    user_limit_key = f"2fa_confirm_user:{tenant_id}:{current_user.id}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")
    if await is_rate_limited(user_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        success = await two_factor_service.confirm_setup(current_user, body.totp_code)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
        return UnifiedResponse(success=True, data={"message": "Two-factor authentication successfully enabled"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/2fa/verify", response_model=UnifiedResponse)
async def verify_2fa(
    request: Request,
    response: Response,
    body: TwoFactorVerifyRequest,
    auth_service: AuthService = Depends(get_auth_service),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"2fa_verify_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        ip = get_client_ip(request)
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")

        from src.core.security import verify_mfa_token
        payload = verify_mfa_token(body.mfa_token)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired 2FA token")
            
        code_challenge = payload.get("code_challenge")
        
        if code_challenge:
            user_id = uuid.UUID(payload["sub"])
            user = await auth_service.user_repo.get_by_id(user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")
                
            is_verified = await two_factor_service.verify_2fa(user, body.totp_code)
            if not is_verified:
                from src.core.metrics import LOGIN_COUNTER
                LOGIN_COUNTER.labels(status="failed", tenant_id=str(tenant_id)).inc()
                from src.core.fingerprint import calculate_device_fingerprint
                fingerprint = calculate_device_fingerprint(ua, ip, lang)
                await auth_service.audit_repo.create(
                    action="login_failed",
                    user_id=user.id,
                    ip_address=ip,
                    user_agent=ua,
                    device_fingerprint=fingerprint,
                    metadata_json={"reason": "invalid_2fa_code"}
                )
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA code")
                
            auth_code = str(uuid.uuid4())
            code_challenge_method = payload.get("code_challenge_method", "S256")
            client_redirect_uri = payload.get("client_redirect_uri")
            client_state = payload.get("client_state")
            
            code_data = {
                "user_id": str(user.id),
                "tenant_id": str(tenant_id),
                "role": user.role,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method
            }
            
            from src.core.redis import init_redis
            import json
            redis_client = await init_redis()
            await redis_client.set(f"oauth_code:{auth_code}", json.dumps(code_data), ex=300)
            
            mobile = is_mobile_client(request)
            if mobile:
                return UnifiedResponse(
                    success=True,
                    data={
                        "code": auth_code,
                        "state": client_state
                    }
                )
            else:
                from fastapi.responses import RedirectResponse
                redirect_url = client_redirect_uri or "http://localhost:3000"
                separator = "&" if "?" in redirect_url else "?"
                state_query = f"&state={client_state}" if client_state else ""
                return UnifiedResponse(
                    success=True,
                    data={
                        "code": auth_code,
                        "state": client_state,
                        "redirect_url": f"{redirect_url}{separator}code={auth_code}{state_query}"
                    }
                )

        login_result = await auth_service.complete_2fa_login(
            mfa_token=body.mfa_token,
            totp_code=body.totp_code,
            two_factor_service=two_factor_service,
            ip_address=ip,
            user_agent=ua,
            accept_language=lang
        )

        access_token = login_result.access_token
        refresh_token = login_result.refresh_token
        session = login_result.session

        mobile = is_mobile_client(request)
        if mobile:
            return UnifiedResponse(
                success=True,
                data={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": {"id": str(session.user_id), "role": "user"}
                }
            )
        else:
            from src.api.v1.auth_utils import set_auth_cookies
            set_auth_cookies(response, access_token, refresh_token)
            return UnifiedResponse(
                success=True,
                data={"message": "Login successful"}
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

@router.post("/2fa/disable", response_model=UnifiedResponse)
async def disable_2fa(
    request: Request,
    body: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"2fa_disable_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 3):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        success = await two_factor_service.disable_2fa(current_user, body.password, body.totp_code)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification failed")
        return UnifiedResponse(success=True, data={"message": "Two-factor authentication disabled"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/2fa/backup-codes/regenerate", response_model=UnifiedResponse)
async def regenerate_backup_codes(
    request: Request,
    current_user: User = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"2fa_regen_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 3):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        new_codes = await two_factor_service.regenerate_backup_codes(current_user)
        return UnifiedResponse(
            success=True,
            data={"backup_codes": new_codes}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
