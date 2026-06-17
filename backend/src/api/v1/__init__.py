from fastapi import APIRouter
from src.api.v1.auth import router as auth_router
from src.api.v1.health import router as health_router

v1_router = APIRouter()
v1_router.include_router(auth_router)
# Note: we can keep health check under prefix or separate it. Let's include it globally in main,
# or under /health. Let's register health_router directly in main for root healthchecks,
# and register auth_router under the standard v1 prefix (/api/v1/auth).
