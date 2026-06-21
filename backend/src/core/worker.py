import asyncio
from arq import cron
from arq.connections import RedisSettings
from src.config import settings
from src.core.logging import logger

redis_settings = RedisSettings(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    database=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD
)

async def startup(ctx):
    from src.database import async_session_maker
    from src.core.http_client import init_http_client
    logger.info("Starting Arq worker...")
    ctx['db_maker'] = async_session_maker
    ctx['http_client'] = await init_http_client()

async def shutdown(ctx):
    from src.core.http_client import close_http_client
    logger.info("Shutting down Arq worker...")
    await close_http_client()

async def garbage_collect_cron(ctx):
    from src.core.tasks import garbage_collect_expired_tokens_once
    db_maker = ctx['db_maker']
    async with db_maker() as session:
        await garbage_collect_expired_tokens_once(session)

async def send_email_task(ctx, email_to: str, subject: str, html_body: str):
    from src.services.email import email_service
    logger.info(f"Arq sending email to {email_to}")
    await email_service.send_email_with_retries(email_to, subject, html_body)

async def dispatch_webhook_task(ctx, delivery_id: str):
    from src.services.webhook import deliver_webhook_background
    import uuid
    logger.info(f"Arq dispatching webhook delivery {delivery_id}")
    await deliver_webhook_background(uuid.UUID(delivery_id))

async def anonymize_audit_logs_cron(ctx):
    from src.core.tasks import anonymize_old_audit_logs
    db_maker = ctx['db_maker']
    async with db_maker() as session:
        await anonymize_old_audit_logs(session)

class WorkerSettings:
    functions = [send_email_task, dispatch_webhook_task]
    cron_jobs = [
        cron(garbage_collect_cron, minute=0),  # Every hour at minute 0
        cron(anonymize_audit_logs_cron, hour=2, minute=0) # Every day at 2:00 AM
    ]
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 100
    job_timeout = 60
