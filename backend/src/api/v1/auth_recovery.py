import uuid
from fastapi import APIRouter, Depends, Request, HTTPException, status
from src.api.deps import (
    get_auth_service,
    get_current_user,
    resolve_tenant,
    get_captcha_service
)
from src.services.auth import AuthService
from src.services.captcha import CaptchaService
from src.models.user import User
from src.core.rate_limit import is_rate_limited
from src.schemas.common import UnifiedResponse
from src.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from src.api.v1.auth_utils import get_client_ip

router = APIRouter()

@router.post("/request-verification", response_model=UnifiedResponse)
async def request_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"email_verify_req_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    user_limit_key = f"email_verify_req_user:{tenant_id}:{current_user.id}"
    
    if await is_rate_limited(ip_limit_key, 3):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification requests. Try again later.")
    if await is_rate_limited(user_limit_key, 2):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification requests. Try again later.")

    try:
        await auth_service.request_email_verification(current_user.id)
        return UnifiedResponse(success=True, data={"message": "Verification email sent"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/verify-email", response_model=UnifiedResponse)
async def verify_email(
    token: str,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    try:
        await auth_service.verify_email(token)
        return UnifiedResponse(success=True, data={"message": "Email verified successfully"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/forgot-password", response_model=UnifiedResponse)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    captcha_service: CaptchaService = Depends(get_captcha_service)
):
    await captcha_service.verify_captcha(body.captcha_token, body.captcha_id, get_client_ip(request))
    ip_limit_key = f"forgot_password_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 3):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many password reset attempts. Try again later.")

    try:
        await auth_service.request_password_reset(body.email)
        return UnifiedResponse(success=True, data={"message": "If the email exists, a password reset link has been sent."})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/reset-password", response_model=UnifiedResponse)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    captcha_service: CaptchaService = Depends(get_captcha_service)
):
    await captcha_service.verify_captcha(body.captcha_token, body.captcha_id, get_client_ip(request))
    ip_limit_key = f"reset_password_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many password reset attempts. Try again later.")

    from src.core.security import check_pwned_password
    if await check_pwned_password(body.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password has appeared in a data breach. Please choose a different password.")

    try:
        await auth_service.reset_password(body.token, body.new_password)
        return UnifiedResponse(success=True, data={"message": "Password reset successfully"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
