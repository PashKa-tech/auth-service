import asyncio
from sqlalchemy import delete, func
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
                # Delete expired verification tokens
                stmt1 = delete(VerificationToken).where(VerificationToken.expires_at < func.now())
                result1 = await session.execute(stmt1)
                
                # Delete expired refresh tokens
                stmt2 = delete(RefreshToken).where(RefreshToken.expires_at < func.now())
                result2 = await session.execute(stmt2)
                
                # Delete expired sessions
                stmt3 = delete(Session).where(Session.expires_at < func.now())
                result3 = await session.execute(stmt3)
                
                await session.commit()
                
                logger.info(f"Garbage collection complete. Deleted: {result1.rowcount} verification tokens, {result2.rowcount} refresh tokens, {result3.rowcount} sessions.")
                
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
