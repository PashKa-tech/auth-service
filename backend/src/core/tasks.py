import asyncio
from sqlalchemy import delete, func, select
from src.database import async_session_factory
from src.models.session import Session
from src.models.token import RefreshToken, VerificationToken
from src.models.tenant import OrganizationInvite
from src.models.webhook import WebhookDelivery
from src.models.audit import AuditLog
from src.core.logging import logger

async def garbage_collect_expired_tokens_once(session):
    """Deletes expired sessions, tokens, invites and old webhooks from the database."""
    try:
        logger.info("Running garbage collection for expired tokens and sessions.")
        deleted_vtokens = 0
        while True:
            stmt1 = delete(VerificationToken).where(
                VerificationToken.id.in_(
                    select(VerificationToken.id).where(VerificationToken.expires_at < func.now()).limit(1000)
                )
            ).execution_options(synchronize_session=False)
            res1 = await asyncio.wait_for(session.execute(stmt1), timeout=5.0)
            deleted_vtokens += res1.rowcount
            await session.commit()
            if res1.rowcount < 1000:
                break
            await asyncio.sleep(0.1)
        
        # Delete expired refresh tokens
        deleted_rtokens = 0
        while True:
            stmt2 = delete(RefreshToken).where(
                RefreshToken.id.in_(
                    select(RefreshToken.id).where(RefreshToken.expires_at < func.now()).limit(1000)
                )
            ).execution_options(synchronize_session=False)
            res2 = await asyncio.wait_for(session.execute(stmt2), timeout=5.0)
            deleted_rtokens += res2.rowcount
            await session.commit()
            if res2.rowcount < 1000:
                break
            await asyncio.sleep(0.1)
        
        # Delete expired sessions
        deleted_sessions = 0
        while True:
            stmt3 = delete(Session).where(
                Session.id.in_(
                    select(Session.id).where(Session.expires_at < func.now()).limit(1000)
                )
            ).execution_options(synchronize_session=False)
            res3 = await asyncio.wait_for(session.execute(stmt3), timeout=5.0)
            deleted_sessions += res3.rowcount
            await session.commit()
            if res3.rowcount < 1000:
                break
            await asyncio.sleep(0.1)

        # Delete expired organization invites
        deleted_invites = 0
        while True:
            stmt4 = delete(OrganizationInvite).where(
                OrganizationInvite.id.in_(
                    select(OrganizationInvite.id).where(OrganizationInvite.expires_at < func.now()).limit(1000)
                )
            ).execution_options(synchronize_session=False)
            res4 = await asyncio.wait_for(session.execute(stmt4), timeout=5.0)
            deleted_invites += res4.rowcount
            await session.commit()
            if res4.rowcount < 1000:
                break
            await asyncio.sleep(0.1)

        # Delete webhook deliveries
        deleted_webhooks = 0
        import datetime
        while True:
            thirty_days_ago = func.now() - datetime.timedelta(days=30)
            stmt5 = delete(WebhookDelivery).where(
                WebhookDelivery.id.in_(
                    select(WebhookDelivery.id).where(
                        WebhookDelivery.created_at < thirty_days_ago
                    ).limit(1000)
                )
            ).execution_options(synchronize_session=False)
            res5 = await asyncio.wait_for(session.execute(stmt5), timeout=5.0)
            deleted_webhooks += res5.rowcount
            await session.commit()
            if res5.rowcount < 1000:
                break
            await asyncio.sleep(0.1)
        
        logger.info(f"Garbage collection complete. Deleted: {deleted_vtokens} verification tokens, {deleted_rtokens} refresh tokens, {deleted_sessions} sessions, {deleted_invites} invites, {deleted_webhooks} old webhook deliveries.")
            
    except Exception as e:
        logger.error(f"Error during garbage collection: {e}")
        _gc_task = None
        logger.info("Stopped background garbage collector task.")

async def anonymize_old_audit_logs(session):
    """Anonymizes PII (IP, User-Agent, etc.) in audit logs older than 90 days."""
    import datetime
    from sqlalchemy import update, cast, JSON
    try:
        ninety_days_ago = func.now() - datetime.timedelta(days=90)
        stmt = (
            update(AuditLog)
            .where(
                AuditLog.timestamp < ninety_days_ago,
                (AuditLog.ip_address.is_not(None)) | (AuditLog.user_agent.is_not(None))
            )
            .values(
                ip_address='0.0.0.0',
                user_agent='Anonymized',
                device_fingerprint='Anonymized',
                metadata_json=cast({"redacted": True}, JSON)
            )
            .execution_options(synchronize_session=False)
        )
        res = await session.execute(stmt)
        await session.commit()
        if res.rowcount > 0:
            logger.info(f"Anonymized PII for {res.rowcount} old audit logs.")
    except Exception as e:
        logger.error(f"Error during audit log anonymization: {e}")
