from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.database import get_db
from src.core.redis import init_redis

router = APIRouter()

@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness_check():
    """Simple check to confirm service is alive."""
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db)):
    """Comprehensive readiness probe checking DB and Redis connectivity."""
    db_ok = False
    redis_ok = False
    details = {}
    
    # Check Database connection
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
        details["database"] = "ok"
    except Exception as e:
        details["database"] = f"error: {str(e)}"
        
    # Check Redis connection
    try:
        redis_client = await init_redis()
        await redis_client.ping()
        redis_ok = True
        details["redis"] = "ok"
    except Exception as e:
        details["redis"] = f"error: {str(e)}"
        
    if not db_ok or not redis_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "details": details}
        
    return {"status": "ready", "details": details}
