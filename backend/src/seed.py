import asyncio
import uuid
import hashlib
from src.database import Base, engine, async_session_factory
from src.models.tenant import Tenant
from src.core.logging import setup_logging, logger

# Fixed seed values for development convenience
DEV_TENANT_ID = uuid.UUID("3a39e7c5-555e-4c7c-87d4-8d96dbeef6a3")
DEV_API_KEY = "default_dev_key"
DEV_API_KEY_HASH = hashlib.sha256(DEV_API_KEY.encode("utf-8")).hexdigest()

async def seed_data():
    setup_logging()
    logger.info("Initializing database tables...")
    
    # Ensure tables are created (fallback if migrations weren't run)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("Seeding default developer tenant...")
    async with async_session_factory() as db:
        # Check if tenant already exists
        from sqlalchemy import select
        res = await db.execute(select(Tenant).where(Tenant.id == DEV_TENANT_ID))
        tenant = res.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                id=DEV_TENANT_ID,
                name="Default Local Tenant",
                api_key=DEV_API_KEY_HASH,
                api_secret_hash="fake_argon2_secret_hash_for_dev_keys"
            )
            db.add(tenant)
            await db.commit()
            logger.info("Successfully seeded Tenant:")
            logger.info(f"  - Tenant ID: {DEV_TENANT_ID}")
            logger.info(f"  - API Key:   {DEV_API_KEY}")
            logger.info(f"  - Header:    X-Api-Key: {DEV_API_KEY}")
        else:
            logger.info("Default local tenant already seeded.")

if __name__ == "__main__":
    asyncio.run(seed_data())
