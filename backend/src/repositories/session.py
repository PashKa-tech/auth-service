import uuid
from datetime import datetime, timezone
import httpx
from user_agents import parse as parse_user_agent
from sqlalchemy import select, update
from src.models.session import Session
from src.models.user import User
from src.repositories.base import TenantScopedRepository

class SessionRepository(TenantScopedRepository):
    async def create(
        self,
        user_id: uuid.UUID,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None
    ) -> Session:
        # Verify user belongs to the tenant first
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == self.tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found in this tenant context.")

        # Parse User Agent
        os_info = None
        browser_info = None
        device_type = None
        
        if user_agent:
            try:
                ua = parse_user_agent(user_agent)
                os_info = f"{ua.os.family} {ua.os.version_string}".strip()
                browser_info = f"{ua.browser.family} {ua.browser.version_string}".strip()
                
                if ua.is_mobile:
                    device_type = "Mobile"
                elif ua.is_tablet:
                    device_type = "Tablet"
                elif ua.is_pc:
                    device_type = "PC"
                elif ua.is_bot:
                    device_type = "Bot"
                else:
                    device_type = "Unknown"
            except Exception:
                pass

        # Fetch Geo IP (Synchronously during session creation, adds ~100-200ms latency but provides immediate security context)
        location = None
        if ip_address and ip_address not in ("127.0.0.1", "::1", "localhost"):
            try:
                # Use ip-api.com for free IP geolocation
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"http://ip-api.com/json/{ip_address}")
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "success":
                            city = data.get("city", "")
                            country = data.get("country", "")
                            location = f"{city}, {country}".strip(", ")
            except Exception as e:
                # Silently fail if geo-ip service is down to not block login
                pass

        session = Session(
            user_id=user_id,
            expires_at=expires_at,
            ip_address=ip_address,
            location=location,
            user_agent=user_agent,
            os_info=os_info,
            browser_info=browser_info,
            device_type=device_type,
            device_fingerprint=device_fingerprint
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        result = await self.db.execute(
            select(Session)
            .join(User, Session.user_id == User.id)
            .where(Session.id == session_id, User.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_active_by_user(self, user_id: uuid.UUID) -> list[Session]:
        result = await self.db.execute(
            select(Session)
            .join(User, Session.user_id == User.id)
            .where(
                Session.user_id == user_id,
                User.tenant_id == self.tenant_id,
                Session.is_revoked == False,
                Session.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
            )
        )
        return list(result.scalars().all())

    async def revoke(self, session_id: uuid.UUID) -> bool:
        # Check if the session exists and belongs to the tenant first
        session = await self.get_by_id(session_id)
        if not session:
            return False
        session.is_revoked = True
        self.db.add(session)
        await self.db.flush()
        return True

    async def revoke_all_by_user(self, user_id: uuid.UUID) -> int:
        # Revoke all sessions for user belonging to this tenant
        result = await self.db.execute(
            update(Session)
            .where(
                Session.user_id == user_id,
                Session.is_revoked == False,
                Session.user_id.in_(
                    select(User.id).where(User.id == user_id, User.tenant_id == self.tenant_id)
                )
            )
            .values(is_revoked=True)
        )
        await self.db.flush()
        return result.rowcount

    async def get_recent_by_user(self, user_id: uuid.UUID, limit: int = 5) -> list[Session]:
        """Get the most recent sessions for a user, sorted by creation time descending."""
        result = await self.db.execute(
            select(Session)
            .join(User, Session.user_id == User.id)
            .where(
                Session.user_id == user_id,
                User.tenant_id == self.tenant_id
            )
            .order_by(Session.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

