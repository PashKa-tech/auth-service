import redis.asyncio as aioredis
from src.config import settings
from src.core.logging import logger

redis_client: aioredis.Redis | None = None

async def init_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is not None:
        return redis_client
        
    if settings.USE_FAKEREDIS:
        import fakeredis.aioredis as fake_aioredis
        logger.info("Initializing Fake Redis client for local development/testing")
        redis_client = fake_aioredis.FakeRedis(decode_responses=True)
    else:
        logger.info(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        redis_client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    return redis_client

async def close_redis():
    global redis_client
    if redis_client is not None:
        logger.info("Closing Redis connection")
        await redis_client.close()
        redis_client = None
