import redis.asyncio as aioredis
from src.config import settings
from src.core.logging import logger

import asyncio

_redis_clients = {}

async def init_redis() -> aioredis.Redis:
    loop = asyncio.get_running_loop()
    if loop in _redis_clients:
        return _redis_clients[loop]
        
    if settings.USE_FAKEREDIS:
        import fakeredis.aioredis as fake_aioredis
        import fakeredis
        logger.info("Initializing Fake Redis client for local development/testing")
        server = fakeredis.FakeServer()
        client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    else:
        logger.info(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
    _redis_clients[loop] = client
    return client

async def close_redis():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if loop in _redis_clients:
        client = _redis_clients.pop(loop)
        logger.info("Closing Redis connection")
        await client.close()
