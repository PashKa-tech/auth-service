import asyncio
from sqlalchemy import delete, func, select
from src.database import async_session_factory
from src.models.session import Session
from src.models.token import RefreshToken, VerificationToken
from src.core.logging import logger

async def garbage_collect_expired_tokens():
    """Periodically deletes expired sessions and tokens from the database."""
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
                    )
                    res1 = await session.execute(stmt1)
                    deleted_vtokens += res1.rowcount
                    if res1.rowcount < 1000:
                        break
                
                # Delete expired refresh tokens
                deleted_rtokens = 0
                while True:
                    stmt2 = delete(RefreshToken).where(
                        RefreshToken.id.in_(
                            select(RefreshToken.id).where(RefreshToken.expires_at < func.now()).limit(1000)
                        )
                    )
                    res2 = await session.execute(stmt2)
                    deleted_rtokens += res2.rowcount
                    if res2.rowcount < 1000:
                        break
                
                # Delete expired sessions
                deleted_sessions = 0
                while True:
                    stmt3 = delete(Session).where(
                        Session.id.in_(
                            select(Session.id).where(Session.expires_at < func.now()).limit(1000)
                        )
                    )
                    res3 = await session.execute(stmt3)
                    deleted_sessions += res3.rowcount
                    if res3.rowcount < 1000:
                        break
                
                await session.commit()
                
                logger.info(f"Garbage collection complete. Deleted: {deleted_vtokens} verification tokens, {deleted_rtokens} refresh tokens, {deleted_sessions} sessions.")
                
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
