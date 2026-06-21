from arq import create_pool
from arq.connections import RedisSettings
from src.config import settings

_arq_pool = None

async def init_arq():
    global _arq_pool
    if settings.USE_FAKEREDIS:
        return None # Return None in tests so we can mock/bypass it
    
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD
    )
    _arq_pool = await create_pool(redis_settings)
    return _arq_pool

async def get_arq_pool():
    if _arq_pool is None and not settings.USE_FAKEREDIS:
        await init_arq()
    return _arq_pool

async def close_arq():
    if _arq_pool:
        await _arq_pool.close()
