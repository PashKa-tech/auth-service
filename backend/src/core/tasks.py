import asyncio
from sqlalchemy import delete, func, select
from src.database import async_session_factory
from src.models.session import Session
from src.models.token import RefreshToken, VerificationToken
from src.models.tenant import OrganizationInvite
from src.models.webhook import WebhookDelivery
from src.core.logging import logger

async def garbage_collect_expired_tokens():
    """Periodically deletes expired sessions, tokens, invites and failed deliveries from the database."""
    while True:
        try:
            logger.info("Running garbage collection for expired tokens and sessions.")
            async with async_session_factory() as session:
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
                from datetime import timedelta
                import datetime
                while True:
                    thirty_days_ago = func.now() - datetime.timedelta(days=30)
                    stmt5 = delete(WebhookDelivery).where(
                        WebhookDelivery.id.in_(
                            select(WebhookDelivery.id).where(
                                (WebhookDelivery.status == "failed") |
                                (WebhookDelivery.created_at < thirty_days_ago)
                            ).limit(1000)
                        )
                    ).execution_options(synchronize_session=False)
                    res5 = await asyncio.wait_for(session.execute(stmt5), timeout=5.0)
                    deleted_webhooks += res5.rowcount
                    await session.commit()
                    if res5.rowcount < 1000:
                        break
                    await asyncio.sleep(0.1)
                
                logger.info(f"Garbage collection complete. Deleted: {deleted_vtokens} verification tokens, {deleted_rtokens} refresh tokens, {deleted_sessions} sessions, {deleted_invites} invites, {deleted_webhooks} failed webhook deliveries.")
                
        except asyncio.CancelledError:
            logger.info("Garbage collection task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error during garbage collection: {e}")
        
        try:
            # Run every hour (3600 seconds)
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Garbage collection task cancelled during sleep.")
            break

_gc_task = None

def start_garbage_collector():
    global _gc_task
    if _gc_task is None:
        loop = asyncio.get_running_loop()
        _gc_task = loop.create_task(garbage_collect_expired_tokens())
        logger.info("Started background garbage collector task.")

async def stop_garbage_collector():
    global _gc_task
    if _gc_task is not None:
        _gc_task.cancel()
        try:
            await _gc_task
        except asyncio.CancelledError:
            pass
        _gc_task = None
        logger.info("Stopped background garbage collector task.")
