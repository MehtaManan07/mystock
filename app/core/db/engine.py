from typing import AsyncGenerator
from app.core.config import config as settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Async SQLAlchemy engine - similar to TypeORM DataSource
engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=(
        NullPool if not (settings.is_production) else None
    ),  # Disable pooling in debug
    future=True,  # Use SQLAlchemy 2.0 features
)

# Session factory - similar to TypeORM's Repository pattern
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # Manual control over flushing
)


async def get_db_util() -> AsyncGenerator[AsyncSession, None]:
    """
    Database dependency for FastAPI.
    Similar to NestJS's @InjectRepository() but as a dependency.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
