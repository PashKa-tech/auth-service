from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, NullPool
from src.config import settings

# Create Async Engine
if not settings.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        connect_args={
            "server_settings": {"jit": "off"},
            "prepared_statement_cache_size": 0,
        }
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.ENV == "development"
    )

# Create Session Factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Declarative Base for models
class Base(DeclarativeBase):
    pass

# DB Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            # Removed unconditional commit on read requests
            pass
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
