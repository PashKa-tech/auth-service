import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.config import settings
from src.core.logging import setup_logging, logger
from src.core.context import set_request_id, get_request_id, set_tenant_id
from src.core.redis import init_redis, close_redis
from src.core.tasks import start_garbage_collector, stop_garbage_collector
from src.core.metrics import REQUEST_LATENCY, http_requests_total, auth_failures_total
from src.core.http_client import init_http_client, close_http_client
from src.api.v1.auth import router as auth_router
from src.api.v1.health import router as health_router
from src.api.v1.organizations import router as organizations_router
from src.api.v1.metrics import router as metrics_router
from src.api.v1.rbac import router as rbac_router
from src.api.v1.saml import router as saml_router
from src.api.v1.oidc import router as oidc_router
from src.api.v1.oauth_apps import router as oauth_apps_router
from src.api.v1.webhooks import router as webhooks_router
from src.api.v1.passwordless import router as passwordless_router
from src.api.v1.scim import router as scim_router
from src.api.v1.actions import router as actions_router
from src.api.v1.saml_connections import router as saml_connections_router
from src.middlewares.rbac import RBACMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("Starting up Auth Service...")
    await init_redis()
    await init_http_client()
    start_garbage_collector()
    yield
    # Shutdown
    logger.info("Shutting down Auth Service...")
    await stop_garbage_collector()
    await close_http_client()
    await close_redis()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from src.core.tracing import init_tracing
init_tracing(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RBACMiddleware)

from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- Middlewares ---

# --- ASGI Middlewares ---
from starlette.types import ASGIApp, Receive, Scope, Send

class PrometheusMetricsMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        if request.url.path == "/metrics":
            return await self.app(scope, receive, send)

        start_time = time.perf_counter()
        status_code = "500"
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = str(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            route = scope.get("route")
            endpoint = route.path if route else "unmatched_route"
            method = scope["method"]

            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
            http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()

            if status_code in ("401", "403"):
                auth_failures_total.inc()

class RequestTracingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope)
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:16]}"
            
        set_request_id(request_id)
        set_tenant_id(None)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)

        await self.app(scope, receive, send_wrapper)

from starlette.datastructures import MutableHeaders
app.add_middleware(PrometheusMetricsMiddleware)
app.add_middleware(RequestTracingMiddleware)



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
app.include_router(passwordless_router, prefix=settings.API_V1_STR + "/auth/passwordless", tags=["passwordless"])
app.include_router(oidc_router, tags=["oidc"])
app.include_router(oauth_apps_router, prefix=settings.API_V1_STR + "/organizations/oauth-apps", tags=["oauth-apps"])
app.include_router(saml_connections_router, prefix=settings.API_V1_STR + "/organizations/saml-connections", tags=["saml-connections"])
app.include_router(webhooks_router, prefix=settings.API_V1_STR + "/organizations/webhooks", tags=["webhooks"])
app.include_router(scim_router, prefix=settings.API_V1_STR + "/scim/v2", tags=["scim"])
app.include_router(actions_router, prefix=settings.API_V1_STR + "/organizations/actions", tags=["actions"])

@app.get("/")
async def root():
    return {"status": "ok", "service": "auth-service"}
