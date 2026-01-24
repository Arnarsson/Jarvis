"""Async database session factory using SQLAlchemy 2.0 patterns."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jarvis_server.config import get_settings

# Create async engine from settings
# echo=False for production (no SQL logging)
engine = create_async_engine(
    get_settings().database_url,
    echo=False,
    pool_pre_ping=True,  # Verify connections before using
)

# Session factory with recommended settings
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit (better for API responses)
    autoflush=False,  # Manual control over flushes
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for async database sessions.

    Usage with FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    The session is automatically closed after the request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
