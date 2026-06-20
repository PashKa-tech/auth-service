from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
import uuid
import secrets
import json

from src.database import get_db
from src.api.deps import resolve_tenant, get_auth_service
from src.models.user import User
from src.core.redis import init_redis as get_redis
from src.services.auth import AuthService
from src.schemas.common import UnifiedResponse
from src.core.logging import logger

router = APIRouter()

class MagicLinkStartRequest(BaseModel):
    email: EmailStr

class MagicLinkVerifyRequest(BaseModel):
    token: str

@router.post("/start", response_model=UnifiedResponse)
async def start_passwordless(
    body: MagicLinkStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant)
):
    """Initiates passwordless login by sending a magic link to the user's email."""
    # Find user
    email_lower = body.email.lower()
    res = await db.execute(select(User).where(User.email == email_lower, User.tenant_id == tenant_id))
    user = res.scalar_one_or_none()
    
    if not user:
        # In a real Auth0 parity system, you can choose to auto-provision accounts via magic link.
        # For security against user enumeration, we return success anyway.
        # But for this demo, we'll create the user if they don't exist to enable smooth UX.
        user = User(
            tenant_id=tenant_id,
            email=email_lower,
            password_hash="passwordless", # No password
            is_verified=True,
            role="user"
        )
        db.add(user)
        await db.flush()
    
    # Generate unique token
    token = secrets.token_urlsafe(32)
    
    # Store in Redis with 15 minutes expiration
    redis = await get_redis()
    key = f"magiclink:{token}"
    data = {
        "user_id": str(user.id),
        "tenant_id": str(tenant_id)
    }
    await redis.set(key, json.dumps(data), ex=900) # 15 minutes
    
    # Mock Email Sending
    magic_link = f"{request.url.scheme}://{request.url.netloc}/verify-magic-link?token={token}"
    logger.info(f"MAGIC LINK for {email_lower}: {magic_link}")
    
    return UnifiedResponse(success=True, message="If an account exists, a magic link has been sent to the email address.")

@router.post("/verify", response_model=UnifiedResponse)
async def verify_passwordless(
    body: MagicLinkVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Verifies a magic link token and returns session tokens."""
    redis = await get_redis()
    key = f"magiclink:{body.token}"
    
    data_str = await redis.get(key)
    if not data_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Magic link token is invalid or has expired."
        )
        
    # Invalidate token immediately to prevent reuse
    await redis.delete(key)
    
    data = json.loads(data_str)
    user_id = uuid.UUID(data["user_id"])
    
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked or inactive."
        )
        
    
    from src.api.v1.auth_utils import get_client_ip
    user_agent = request.headers.get("User-Agent")
    client_ip = get_client_ip(request)
    
    tokens = await auth_service.login_user(user, user_agent, client_ip)
    return UnifiedResponse(success=True, data=tokens, message="Successfully authenticated via magic link.")
