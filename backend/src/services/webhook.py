import json
import hmac
import hashlib
import httpx
from src.core.http_client import http_client
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import BackgroundTasks
from urllib.parse import urlparse
import ipaddress
import socket
import asyncio

from src.models.webhook import WebhookEndpoint, WebhookDelivery
from src.core.logging import logger
from src.database import async_session_factory
from src.core.queue import get_arq_pool

async def deliver_webhook_background(delivery_id: uuid.UUID):
    try:
        async with async_session_factory() as db:
            result = await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
            delivery = result.scalar_one_or_none()
            if not delivery:
                return
                
            result_ep = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == delivery.endpoint_id))
            endpoint = result_ep.scalar_one_or_none()
            if not endpoint:
                return

            service = WebhookService(db)
            if not await service._is_safe_url(endpoint.url):
                delivery.status = "failed"
                delivery.last_error = "Unsafe or internal URL blocked by SSRF protection"
                delivery.attempt_count += 1
                db.add(delivery)
                await db.commit()
                return

            signature = service._generate_signature(delivery.payload, endpoint.secret_key)
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }

            delivery.attempt_count += 1
            
            try:
                from src.core import http_client as http_client_module
                client_to_use = http_client_module.http_client
                
                if client_to_use:
                    response = await client_to_use.post(
                        endpoint.url,
                        json=delivery.payload,
                        headers=headers
                    )
                else:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(
                            endpoint.url,
                            json=delivery.payload,
                            headers=headers
                        )
                        
                response.raise_for_status()
                    
                delivery.status = "success"
                delivery.last_error = None
            except Exception as e:
                delivery.status = "failed"
                delivery.last_error = str(e)
                db.add(delivery)
                await db.commit()
                raise  # Raise so arq handles it
    except Exception as e:
        logger.error(f"Failed to execute background webhook delivery: {e}")
        raise


class WebhookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_signature(self, payload: dict[str, Any], secret_key: str) -> str:
        """
        Generate HMAC SHA-256 signature for the given payload using the secret key.
        The payload is serialized to a compact JSON string.
        """
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        secret_bytes = secret_key.encode("utf-8")
        signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
        return signature

    async def _is_safe_url(self, url: str) -> bool:
        """Prevent SSRF by rejecting local/private IP addresses or malformed URLs."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            
            hostname = parsed.hostname
            if not hostname:
                return False

            loop = asyncio.get_running_loop()
            addr_info = await loop.getaddrinfo(hostname, None)
            ip = addr_info[0][4][0]
            ip_obj = ipaddress.ip_address(ip)
            
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
                return False
                
            return True
        except Exception:
            return False

    async def dispatch_event(self, background_tasks: BackgroundTasks, tenant_id: uuid.UUID, event_type: str, payload: dict[str, Any]) -> None:
        """
        Dispatches an event to all subscribed webhook endpoints for a given tenant.
        """
        result = await self.db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.tenant_id == tenant_id)
        )
        endpoints = result.scalars().all()
        
        deliveries = []
        for endpoint in endpoints:
            if not endpoint.events_list or event_type in endpoint.events_list or "*" in endpoint.events_list:
                delivery = WebhookDelivery(
                    endpoint_id=endpoint.id,
                    payload=payload,
                    status="pending",
                    attempt_count=0
                )
                self.db.add(delivery)
                deliveries.append(delivery)
                
        if deliveries:
            await self.db.commit()
            
            pool = await get_arq_pool()
            for delivery in deliveries:
                await self.db.refresh(delivery)
                if pool:
                    await pool.enqueue_job('dispatch_webhook_task', str(delivery.id))
                else:
                    background_tasks.add_task(deliver_webhook_background, delivery.id)
