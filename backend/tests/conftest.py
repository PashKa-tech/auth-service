import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import uuid
import hashlib
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from src.config import settings

# Override settings for testing
TEST_DB_URL = "sqlite+aiosqlite:///file:testmemdb?mode=memory&cache=shared&uri=true"
settings.DATABASE_URL = TEST_DB_URL
settings.ENV = "testing"
settings.USE_FAKEREDIS = True

from src.database import Base, get_db
from src.models.tenant import Tenant
from src.main import app

# Create async engine with shared cache
test_engine = create_async_engine(
    TEST_DB_URL, 
    connect_args={"check_same_thread": False, "timeout": 15},
    poolclass=StaticPool
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Test tenant credentials
TEST_TENANT_ID = uuid.uuid4()
TEST_API_KEY = "test_developer_key"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode("utf-8")).hexdigest()



@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables and seed a default test tenant."""
    # Keep one connection open to prevent SQLite from dropping the shared in-memory database
    keep_alive_conn = await test_engine.connect()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Seed default tenant
    async with TestSessionLocal() as db:
        # Check if tenant already exists (safety)
        from sqlalchemy import select
        res = await db.execute(select(Tenant).where(Tenant.id == TEST_TENANT_ID))
        if not res.scalar_one_or_none():
            tenant = Tenant(
                id=TEST_TENANT_ID,
                name="Test Corporate Tenant"
            )
            db.add(tenant)
            
            from src.models.tenant import TenantApiKey
            api_key = TenantApiKey(
                tenant_id=TEST_TENANT_ID,
                name="Test Key",
                key_prefix="test_",
                api_key_hash=TEST_API_KEY_HASH
            )
            db.add(api_key)
            await db.commit()
            
    yield
    
    await keep_alive_conn.close()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean DB session for test validations."""
    async with TestSessionLocal() as session:
        yield session

# Override get_db dependency in the FastAPI application
async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def mock_pwned_password(monkeypatch):
    """Automatically mock check_pwned_password to always return False during tests."""
    from src.core import security
    async def mock_check(*args, **kwargs):
        return False
    monkeypatch.setattr(security, "check_pwned_password", mock_check)

@pytest.fixture(autouse=True)
def mock_async_session_factory(monkeypatch):
    """Automatically mock async_session_factory to use TestSessionLocal to prevent database locked errors."""
    from src.repositories import audit
    import contextlib
    
    @contextlib.asynccontextmanager
    async def mock_factory():
        async with TestSessionLocal() as session:
            yield session
            
    monkeypatch.setattr(audit, "async_session_factory", mock_factory)

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX async client to test endpoints."""
    # Using ASGITransport for modern HTTPX (since app is ASGI)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as ac:
        yield ac
