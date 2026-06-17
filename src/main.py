import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.config import settings
from src.core.logging import setup_logging, logger
from src.core.context import set_request_id, get_request_id, set_tenant_id
from src.core.redis import init_redis, close_redis
from src.api.v1.auth import router as auth_router
from src.api.v1.health import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("Starting up Auth Service...")
    await init_redis()
    yield
    # Shutdown
    logger.info("Shutting down Auth Service...")
    await close_redis()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Middlewares ---

@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    """Middleware to inject X-Request-ID and handle context variables lifecycle."""
    # Retrieve request ID or generate a new one
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        
    # Bind request_id to contextvar
    set_request_id(request_id)
    
    # Initialize tenant_id context as None for safety
    set_tenant_id(None)
    
    response = await call_next(request)
    
    # Attach X-Request-ID to response headers
    response.headers["X-Request-ID"] = request_id
    return response

# --- Exception Handlers ---

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "details": {}
            },
            "meta": {"version": "v1", "request_id": get_request_id()}
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Simplify validation error details for response
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "issue": error.get("msg", "Validation failed")
        })
        
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": details
            },
            "meta": {"version": "v1", "request_id": get_request_id()}
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": {}
            },
            "meta": {"version": "v1", "request_id": get_request_id()}
        }
    )

# --- Routes Registration ---

# Global health checks
app.include_router(health_router)

# Versioned API routes
app.include_router(auth_router, prefix=settings.API_V1_STR)
