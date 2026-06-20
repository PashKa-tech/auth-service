from fastapi import APIRouter, Depends, HTTPException
from src.schemas.common import UnifiedResponse
from src.config import settings
from src.services.captcha import CaptchaService
from src.api.deps import get_captcha_service

# Import sub-routers
from src.api.v1.auth_basic import router as basic_router
from src.api.v1.auth_oauth import router as oauth_router
from src.api.v1.auth_recovery import router as recovery_router
from src.api.v1.auth_mfa import router as mfa_router
from src.api.v1.auth_webauthn import router as webauthn_router
from src.api.v1.auth_session import router as session_router

router = APIRouter()

# Include sub-routers
router.include_router(basic_router)
router.include_router(oauth_router)
router.include_router(recovery_router)
router.include_router(mfa_router)
router.include_router(webauthn_router)
router.include_router(session_router)

@router.get("/admin-only", response_model=UnifiedResponse)
async def admin_only_route(current_user=Depends(require_role("admin"))):
    return UnifiedResponse(success=True, data={"message": "Welcome, Admin!"})

# Config and Captcha Endpoints
@router.get("/config", response_model=UnifiedResponse)
async def get_auth_config():
    return UnifiedResponse(success=True, data={
        "captcha_type": settings.CAPTCHA_TYPE,
        "recaptcha_site_key": settings.GOOGLE_RECAPTCHA_SITE_KEY
    })

@router.get("/captcha", response_model=UnifiedResponse)
async def get_custom_captcha(captcha_service: CaptchaService = Depends(get_captcha_service)):
    if settings.CAPTCHA_TYPE != "custom":
        raise HTTPException(status_code=400, detail="Custom captcha is not enabled")
    data = await captcha_service.generate_custom_captcha()
    return UnifiedResponse(success=True, data=data)
