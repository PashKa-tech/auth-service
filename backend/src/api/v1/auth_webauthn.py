import uuid
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from src.api.deps import (
    get_auth_service,
    get_current_user,
    resolve_tenant,
    get_webauthn_service
)
from src.services.auth import AuthService
from src.models.user import User
from src.core.rate_limit import is_rate_limited
from src.schemas.common import UnifiedResponse
from src.schemas.auth import WebAuthnLoginBeginRequest, WebAuthnRegisterCompleteRequest, WebAuthnLoginCompleteRequest
from src.api.v1.auth_utils import get_client_ip, is_mobile_client, set_auth_cookies

router = APIRouter()

@router.get("/webauthn/register/begin", response_model=UnifiedResponse)
async def webauthn_register_begin(
    request: Request,
    current_user: User = Depends(get_current_user),
    webauthn_service: "WebAuthnService" = Depends(get_webauthn_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"webauthn_reg_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        options = await webauthn_service.begin_registration(current_user)
        return UnifiedResponse(success=True, data=options)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/webauthn/register/complete", response_model=UnifiedResponse)
async def webauthn_register_complete(
    request: Request,
    body: WebAuthnRegisterCompleteRequest,
    current_user: User = Depends(get_current_user),
    webauthn_service: "WebAuthnService" = Depends(get_webauthn_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"webauthn_reg_c_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        credential = await webauthn_service.complete_registration(current_user, body.response, body.name)
        return UnifiedResponse(success=True, data={"message": "Passkey registered successfully", "id": str(credential.id)})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/webauthn/login/begin", response_model=UnifiedResponse)
async def webauthn_login_begin(
    request: Request,
    body: WebAuthnLoginBeginRequest,
    webauthn_service: "WebAuthnService" = Depends(get_webauthn_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"webauthn_log_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        options = await webauthn_service.begin_login(body.email)
        return UnifiedResponse(success=True, data=options)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/webauthn/login/complete", response_model=UnifiedResponse)
async def webauthn_login_complete(
    request: Request,
    response: Response,
    body: WebAuthnLoginCompleteRequest,
    webauthn_service: "WebAuthnService" = Depends(get_webauthn_service),
    auth_service: AuthService = Depends(get_auth_service),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    ip_limit_key = f"webauthn_log_c_ip:{tenant_id}:{get_client_ip(request) or 'unknown'}"
    if await is_rate_limited(ip_limit_key, 5):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    try:
        ip = get_client_ip(request)
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        
        login_result = await webauthn_service.complete_login(body.email, body.response, ip, ua, lang)

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
            set_auth_cookies(response, access_token, refresh_token)
            return UnifiedResponse(
                success=True,
                data={"message": "Login successful via Passkey"}
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
