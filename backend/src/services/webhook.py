import json
import hmac
import hashlib
import httpx
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.webhook import WebhookEndpoint, WebhookDelivery

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

    async def dispatch_event(self, tenant_id: uuid.UUID, event_type: str, payload: dict[str, Any]) -> None:
        """
        Dispatches an event to all subscribed webhook endpoints for a given tenant.
        """
        # Fetch all endpoints for this tenant
        result = await self.db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.tenant_id == tenant_id)
        )
        endpoints = result.scalars().all()

        for endpoint in endpoints:
            # Check if endpoint is subscribed to this event (or if events_list is wildcard)
            # events_list is expected to be a list of strings
            if not endpoint.events_list or event_type in endpoint.events_list or "*" in endpoint.events_list:
                # Create Delivery record
                delivery = WebhookDelivery(
                    endpoint_id=endpoint.id,
                    payload=payload,
                    status="pending",
                    attempt_count=0
                )
                self.db.add(delivery)
                await self.db.commit()
                await self.db.refresh(delivery)

                # Attempt delivery
                await self._deliver(endpoint, delivery)

    async def _deliver(self, endpoint: WebhookEndpoint, delivery: WebhookDelivery) -> None:
        """
        Attempts to deliver the webhook payload to the endpoint.
        """
        signature = self._generate_signature(delivery.payload, endpoint.secret_key)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature
        }

        # Update delivery attempt count
        delivery.attempt_count += 1
        
        try:
            # Send payload using httpx. We use a 10s timeout to avoid hanging forever.
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
            
        self.db.add(delivery)
        await self.db.commit()
