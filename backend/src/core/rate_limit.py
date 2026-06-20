from src.core.redis import init_redis
from src.core.logging import logger
from fastapi import Request, Depends, HTTPException, status
import uuid

# Forward declaration for dependency, imported locally to avoid circular imports
# from src.api.deps import resolve_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db

async def is_rate_limited(key: str, limit: int, window_seconds: int = 60) -> bool:
    """
    Check if a request rate limit is exceeded for a given key.
    Uses atomic increment and handles Redis failures gracefully (resilience).
    """
    from src.config import settings
    if settings.ENV == "testing":
        return False

    client = await init_redis()
    try:
        # Atomic check and increment using pipeline
        key_name = f"auth_limit:{key}"
        current = await client.get(key_name)
        
        if current is not None and int(current) >= limit:
            return True
            
        async with client.pipeline(transaction=True) as pipe:
            await pipe.incr(key_name)
            if current is None:
                await pipe.expire(key_name, window_seconds)
            await pipe.execute()
            
        return False
    except Exception as e:
        logger.error(f"Rate limiter error for key {key}: {str(e)}. Permitting request (fallback).")
        # Fail open: do not block users if Redis is down
        return False


class RateLimiter:
    """
    Declarative FastAPI Dependency for rate limiting.
    Example: @router.post("/login", dependencies=[Depends(RateLimiter("login_ip", 5))])
    """
    def __init__(self, key_prefix: str, limit: int, window_seconds: int = 60, by_ip: bool = True, by_user: bool = False):
        self.key_prefix = key_prefix
        self.limit = limit
        self.window_seconds = window_seconds
        self.by_ip = by_ip
        self.by_user = by_user

    async def __call__(self, request: Request, db: AsyncSession = Depends(get_db)):
        from src.core.context import get_tenant_id
        from src.models.tenant import Tenant
        from sqlalchemy import select
        try:
            tenant_id_val = get_tenant_id()
            tenant_id = str(tenant_id_val) if tenant_id_val else "global"
        except Exception:
            tenant_id_val = None
            tenant_id = "global"
            
        limit = self.limit
        if tenant_id_val:
            try:
                stmt = select(Tenant.rate_limit_rpm).where(Tenant.id == tenant_id_val)
                result = await db.execute(stmt)
                tenant_limit = result.scalar_one_or_none()
                if tenant_limit is not None:
                    limit = tenant_limit
            except Exception as e:
                logger.error(f"Failed to fetch tenant rate limit for {tenant_id_val}: {str(e)}")
        
        key_parts = [self.key_prefix, str(tenant_id)]
        
        if self.by_ip:
            ip = request.headers.get("X-Forwarded-For")
            if ip:
                ip = ip.split(",")[0].strip()
            else:
                ip = request.client.host if request.client else "unknown"
            key_parts.append(ip)
            
        if self.by_user:
            # Try to get user_id from state
            user_id = getattr(request.state, "user_id", "anonymous")
            key_parts.append(str(user_id))
            
        key = ":".join(key_parts)
        
        if await is_rate_limited(key, limit, self.window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later."
            )
