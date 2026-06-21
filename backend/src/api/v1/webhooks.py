from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
import secrets

from src.database import get_db
from src.api.deps import resolve_tenant, RoleChecker
from src.models.user import User
from src.models.webhook import WebhookEndpoint, WebhookDelivery
from src.schemas.common import UnifiedResponse

router = APIRouter()
admin_only = RoleChecker(["admin", "manager"])

class WebhookCreate(BaseModel):
    url: str
    events_list: list[str]

@router.get("", response_model=UnifiedResponse)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """List all webhook endpoints for the tenant."""
    res = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.tenant_id == tenant_id))
    endpoints = res.scalars().all()
    
    return UnifiedResponse(success=True, data=[
        {
            "id": w.id,
            "url": w.url,
            "events_list": w.events_list
        } for w in endpoints
    ])

@router.post("", response_model=UnifiedResponse)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Create a new webhook endpoint."""
    secret = f"whsec_{secrets.token_urlsafe(24)}"
    
    webhook = WebhookEndpoint(
        tenant_id=tenant_id,
        url=body.url,
        secret_key=secret,
        events_list=body.events_list
    )
    db.add(webhook)
    await db.commit()
    
    return UnifiedResponse(success=True, data={
        "id": webhook.id,
        "url": webhook.url,
        "secret_key": secret, # only returned once
        "events_list": webhook.events_list
    })

@router.delete("/{webhook_id}", response_model=UnifiedResponse)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """Delete a webhook endpoint."""
    res = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == webhook_id, WebhookEndpoint.tenant_id == tenant_id))
    webhook = res.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
        
    await db.delete(webhook)
    await db.commit()
    
    return UnifiedResponse(success=True, message="Webhook deleted successfully")

@router.get("/deliveries", response_model=UnifiedResponse)
async def list_webhook_deliveries(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(resolve_tenant),
    current_user: User = Depends(admin_only)
):
    """List recent webhook deliveries for the tenant."""
    res = await db.execute(
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookDelivery.endpoint_id == WebhookEndpoint.id)
        .where(WebhookEndpoint.tenant_id == tenant_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    deliveries = res.scalars().all()
    
    return UnifiedResponse(success=True, data=[
        {
            "id": d.id,
            "endpoint_id": d.endpoint_id,
            "payload": d.payload,
            "status": d.status,
            "attempt_count": d.attempt_count,
            "last_error": d.last_error,
            "created_at": d.created_at.isoformat() if d.created_at else None
        } for d in deliveries
    ])
