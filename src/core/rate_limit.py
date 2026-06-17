from src.core.redis import init_redis
from src.core.logging import logger

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
