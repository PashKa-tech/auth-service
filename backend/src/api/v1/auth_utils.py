from fastapi import Request, Response
from src.config import settings
from src.schemas.common import UnifiedResponse

def get_client_ip(request: Request) -> str | None:
    """Extract client IP, taking X-Forwarded-For header into account for proxies."""
    ip = request.headers.get("X-Forwarded-For")
    if ip:
        if "," in ip:
            return ip.split(",")[0].strip()
        return ip.strip()
    return request.client.host if request.client else None

def is_mobile_client(request: Request) -> bool:
    """Helper to detect if client is mobile/API based on header."""
    return request.headers.get("X-Client-Type") == "mobile"

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set secure httpOnly cookies for browser clients."""
    is_prod = settings.ENV == "production"
    # Access Token: httpOnly, Secure (in prod), SameSite=Lax, TTL ~ 15m
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=15 * 60, # 15 minutes
    )
    # Refresh Token: httpOnly, Secure (in prod), SameSite=Strict, TTL ~ 7d
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="strict",
        max_age=7 * 24 * 60 * 60, # 7 days
    )

def clear_auth_cookies(response: Response):
    """Clear cookies on logout."""
    response.delete_cookie("access_token", httponly=True, samesite="lax")
    response.delete_cookie("refresh_token", httponly=True, samesite="strict")

def handle_auth_success_response(
    request: Request,
    response: Response,
    access_token: str,
    refresh_token: str,
    user_id: str,
    role: str,
    message: str = "Login successful"
) -> UnifiedResponse:
    if is_mobile_client(request):
        return UnifiedResponse(
            success=True,
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": {"id": user_id, "role": role}
            }
        )
    else:
        set_auth_cookies(response, access_token, refresh_token)
        return UnifiedResponse(
            success=True,
            data={"message": message}
        )

