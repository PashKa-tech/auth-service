import uuid
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse
from src.api.deps import (
    get_auth_service,
    get_oauth_service_dep,
    resolve_tenant,
    requires_fresh_auth
)
from src.services.auth import AuthService
from src.services.oauth import OAuthService
from src.models.user import User
from src.schemas.common import UnifiedResponse
from src.config import settings
from src.core.logging import logger
from src.api.v1.auth_utils import get_client_ip, is_mobile_client, set_auth_cookies

router = APIRouter()

@router.get("/oauth/{provider}")
async def oauth_login(
    provider: str,
    response: Response,
    state: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
    redirect_uri: str | None = None,
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    supported_providers = {"google", "github", "discord", "apple", "facebook", "twitter", "amazon"}
    if provider not in supported_providers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported OAuth provider: {provider}")

    enabled = getattr(settings, f"ENABLE_{provider.upper()}_OAUTH", False)
    if not enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth provider {provider} is disabled")
        
    client_id = getattr(settings, f"{provider.upper()}_CLIENT_ID", None)
    if not client_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth provider {provider} is not configured")

    internal_state = str(uuid.uuid4())
    
    extra_params = {}
    twitter_verifier = None
    if provider == "twitter":
        import secrets
        import hashlib
        import base64
        twitter_verifier = secrets.token_urlsafe(32)
        hashed = hashlib.sha256(twitter_verifier.encode("ascii")).digest()
        twitter_challenge = base64.urlsafe_b64encode(hashed).decode("utf-8").replace("=", "")
        extra_params["code_challenge"] = twitter_challenge
        extra_params["code_challenge_method"] = "S256"

    from src.core.redis import init_redis
    import json
    try:
        redis_client = await init_redis()
        flow_data = {
            "tenant_id": str(tenant_id),
            "client_state": state,
            "client_redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method or "S256"
        }
        if twitter_verifier:
            flow_data["twitter_code_verifier"] = twitter_verifier
        await redis_client.set(f"oauth_state:{internal_state}", json.dumps(flow_data), ex=600)
    except Exception as e:
        logger.error(f"Failed to cache OAuth state: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

    try:
        auth_url = oauth_service.get_authorization_url(provider, internal_state, extra_params=extra_params)
        redirect_response = RedirectResponse(url=auth_url)
        redirect_response.set_cookie(
            key="oauth_state_csrf",
            value=internal_state,
            httponly=True,
            secure=(settings.ENV == "production"),
            samesite="lax",
            max_age=600
        )
        return redirect_response
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
    supported_providers = {"google", "github", "discord", "apple", "facebook", "twitter", "amazon"}
    if provider not in supported_providers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported OAuth provider: {provider}")

    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing state parameter")
        
    cookie_state = request.cookies.get("oauth_state_csrf")
    if not cookie_state or cookie_state != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth CSRF validation failed")
        
    from src.core.redis import init_redis
    import json
    try:
        redis_client = await init_redis()
        state_data_json = await redis_client.get(f"oauth_state:{state}")
        if not state_data_json:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state (CSRF verification failed)")
            
        state_data = json.loads(state_data_json)
        await redis_client.delete(f"oauth_state:{state}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve/delete OAuth state from Redis: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
        
    client_state = state_data.get("client_state")
    client_redirect_uri = state_data.get("client_redirect_uri")
    code_challenge = state_data.get("code_challenge")
    code_challenge_method = state_data.get("code_challenge_method")
    twitter_verifier = state_data.get("twitter_code_verifier")

    redirect_url = client_redirect_uri or "http://localhost:3000"
    if not client_redirect_uri and client_state and (client_state.startswith("http://") or client_state.startswith("https://")):
        redirect_url = client_state

    try:
        current_user = None
        token = request.cookies.get("access_token")
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        if token:
            from src.core.security import verify_access_token
            payload = verify_access_token(token)
            if payload:
                user_id_str = payload.get("sub")
                if user_id_str:
                    try:
                        current_user = await auth_service.user_repo.get_by_id(uuid.UUID(user_id_str))
                    except ValueError:
                        pass

        from src.services.oauth import get_provider_redirect_uri
        redirect_uri = get_provider_redirect_uri(provider)
        user_info = await oauth_service.get_user_info_from_provider(
            provider=provider,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=twitter_verifier
        )
        
        user = await oauth_service.resolve_oauth_user(
            provider=provider,
            provider_user_id=user_info.provider_id,
            email=user_info.email,
            auth_service=auth_service,
            current_user=current_user
        )
        
        from datetime import datetime, timedelta, timezone
        from src.core.security import create_access_token, generate_opaque_token, hash_opaque_token
        from src.core.fingerprint import calculate_device_fingerprint
        
        ip = get_client_ip(request)
        ua = request.headers.get("User-Agent")
        lang = request.headers.get("Accept-Language")
        fingerprint = calculate_device_fingerprint(ua, ip, lang)
        
        if user.is_two_factor_enabled:
            from src.core.security import create_mfa_token
            extra = {}
            if code_challenge:
                extra = {
                    "code_challenge": code_challenge,
                    "code_challenge_method": code_challenge_method,
                    "client_redirect_uri": redirect_url,
                    "client_state": client_state
                }
            mfa_token = create_mfa_token(user.id, tenant_id, extra_payload=extra)
            await auth_service.audit_repo.create(
                action="2fa_challenge_issued",
                user_id=user.id,
                ip_address=ip,
                user_agent=ua,
                device_fingerprint=fingerprint,
                metadata_json={"method": f"oauth_{provider}"}
            )
            mobile = is_mobile_client(request)
            if mobile:
                return UnifiedResponse(
                    success=True,
                    data={
                        "requires_2fa": True,
                        "mfa_token": mfa_token
                    }
                )
            else:
                separator = "&" if "?" in redirect_url else "?"
                redirect_resp = RedirectResponse(
                    url=f"{redirect_url}{separator}requires_2fa=true&mfa_token={mfa_token}"
                )
                return redirect_resp

        if code_challenge:
            auth_code = str(uuid.uuid4())
            code_data = {
                "user_id": str(user.id),
                "tenant_id": str(tenant_id),
                "role": user.role,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method
            }
            try:
                await redis_client.set(f"oauth_code:{auth_code}", json.dumps(code_data), ex=300)
            except Exception as e:
                logger.error(f"Failed to save oauth code: {str(e)}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
                
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
                separator = "&" if "?" in redirect_url else "?"
                state_query = f"&state={client_state}" if client_state else ""
                return RedirectResponse(url=f"{redirect_url}{separator}code={auth_code}{state_query}")

        session_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session = await auth_service.session_repo.create(
            user_id=user.id,
            expires_at=session_expiry,
            ip_address=ip,
            user_agent=ua,
            device_fingerprint=fingerprint
        )
        
        raw_refresh = generate_opaque_token()
        refresh_hash = hash_opaque_token(raw_refresh)
        family_id = str(uuid.uuid4())
        
        await auth_service.token_repo.create(
            session_id=session.id,
            token_hash=refresh_hash,
            family_id=family_id,
            expires_at=session_expiry
        )
        
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
            response.delete_cookie("oauth_state_csrf")
            return UnifiedResponse(
                success=True,
                data={
                    "access_token": access_token,
                    "refresh_token": raw_refresh,
                    "user": {"id": str(user.id), "role": user.role}
                }
            )
        else:
            redirect_resp = RedirectResponse(url=redirect_url)
            redirect_resp.delete_cookie("oauth_state_csrf")
            set_auth_cookies(redirect_resp, access_token, raw_refresh)
            return redirect_resp

    except ValueError as e:
        logger.error(f"OAuth callback resolution failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/me/linked-accounts", response_model=UnifiedResponse)
async def list_linked_accounts(
    current_user: User = Depends(requires_fresh_auth),
    oauth_service: OAuthService = Depends(get_oauth_service_dep)
):
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
    current_user: User = Depends(requires_fresh_auth),
    oauth_service: OAuthService = Depends(get_oauth_service_dep),
    auth_service: AuthService = Depends(get_auth_service)
):
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
