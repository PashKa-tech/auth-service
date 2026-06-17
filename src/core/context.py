import contextvars
from uuid import UUID

# Context variables for global request tracing and multi-tenant scoping
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
tenant_id_ctx: contextvars.ContextVar[UUID | None] = contextvars.ContextVar("tenant_id", default=None)

def get_request_id() -> str:
    return request_id_ctx.get()

def set_request_id(request_id: str) -> None:
    request_id_ctx.set(request_id)

def get_tenant_id() -> UUID | None:
    return tenant_id_ctx.get()

def set_tenant_id(tenant_id: UUID | None) -> None:
    tenant_id_ctx.set(tenant_id)
