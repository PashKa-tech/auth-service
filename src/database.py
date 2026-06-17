from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from src.config import settings

# Determine if we're using SQLite or Postgres
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Create Async Engine
# For SQLite, we must use a single connection thread pool or disable pool check,
# but using defaults with check_same_thread=False is standard for aiosqlite.
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.ENV == "development",
)

# For SQLite, we MUST explicitly enable foreign keys on connection
if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
