import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from src.config import settings
from src.core.logging import setup_logging, logger
from src.core.context import set_request_id, get_request_id, set_tenant_id
from src.core.redis import init_redis, close_redis
from src.core.tasks import start_garbage_collector, stop_garbage_collector
from src.core.metrics import REQUEST_LATENCY, http_requests_total, http_request_duration_seconds, auth_failures_total
from src.api.v1.auth import router as auth_router
from src.api.v1.health import router as health_router
from src.api.v1.organizations import router as organizations_router
from src.api.v1.metrics import router as metrics_router
from src.api.v1.rbac import router as rbac_router
from src.api.v1.saml import router as saml_router
from src.middlewares.rbac import RBACMiddleware

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("Starting up Auth Service...")
    await init_redis()
    start_garbage_collector()
    yield
    # Shutdown
    logger.info("Shutting down Auth Service...")
    await stop_garbage_collector()
    await close_redis()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RBACMiddleware)

# --- Middlewares ---

@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    """Middleware to measure HTTP request metrics."""
    # Exclude metrics endpoint to prevent noise
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    # Get path template if available, else fallback to raw path
    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path
    method = request.method
    status_code = str(response.status_code)

    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    if response.status_code in (401, 403):
        auth_failures_total.inc()

    return response

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

# Register API routers
app.include_router(metrics_router)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(organizations_router, prefix=settings.API_V1_STR + "/organizations", tags=["organizations"])
app.include_router(rbac_router, prefix=settings.API_V1_STR + "/rbac", tags=["rbac"])
app.include_router(saml_router, prefix=settings.API_V1_STR + "/auth", tags=["saml"])
