"""
SQLite Database Engine Configuration for FastAPI.

Optimized for:
- 5-10 concurrent users with WAL mode
- Async operations via aiosqlite
- Safe concurrency with busy_timeout
- Foreign key enforcement
"""

from typing import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import config as settings


def _get_engine_options(database_url: str) -> dict:
    """
    Get engine options based on database type.
    SQLite requires special handling for async and concurrency.
    """
    is_sqlite = database_url.startswith("sqlite")
    
    options = {
        "echo": False,
        "future": True,  # Use SQLAlchemy 2.0 features
    }
    
    if is_sqlite:
        # SQLite-specific configuration
        # NullPool is required for aiosqlite - it doesn't support connection pooling
        # StaticPool can be used for in-memory databases
        if ":memory:" in database_url:
            options["poolclass"] = StaticPool
            options["connect_args"] = {"check_same_thread": False}
        else:
            options["poolclass"] = NullPool
    else:
        # PostgreSQL configuration (fallback)
        options["poolclass"] = NullPool if not settings.is_production else None
    
    return options


def _configure_sqlite_connection(dbapi_connection, connection_record):
    """
    Configure SQLite connection with optimal settings for concurrency.
    Called on every new connection to the database.
    
    Settings:
    - WAL mode: Allows concurrent reads during writes (critical for multi-user)
    - busy_timeout: Wait up to 30s for locks instead of immediate failure
    - foreign_keys: Enforce referential integrity
    - synchronous=NORMAL: Good balance of safety and performance with WAL
    - cache_size: Increase cache for better read performance
    """
    cursor = dbapi_connection.cursor()
    
    # Enable Write-Ahead Logging for concurrent access
    # WAL allows readers to not block writers and vice versa
    cursor.execute("PRAGMA journal_mode=WAL")
    
    # Wait up to 30 seconds for locks before failing
    # Essential for avoiding "database is locked" errors
    cursor.execute("PRAGMA busy_timeout=30000")
    
    # Enforce foreign key constraints (disabled by default in SQLite)
    cursor.execute("PRAGMA foreign_keys=ON")
    
    # NORMAL synchronous is safe with WAL mode and faster than FULL
    cursor.execute("PRAGMA synchronous=NORMAL")
    
    # Increase cache size for better performance (negative = KB, positive = pages)
    # -64000 = 64MB cache
    cursor.execute("PRAGMA cache_size=-64000")
    
    # Enable memory-mapped I/O for faster reads (256MB)
    cursor.execute("PRAGMA mmap_size=268435456")
    
    cursor.close()


# Build the database URL - support both SQLite and PostgreSQL
database_url = settings.database_url

# Create async engine with appropriate configuration
engine = create_async_engine(
    database_url,
    **_get_engine_options(database_url)
)

# Register SQLite-specific event listener if using SQLite
if database_url.startswith("sqlite"):
    # For aiosqlite, we need to use the sync_engine's pool events
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        _configure_sqlite_connection(dbapi_connection, connection_record)


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
    
    Transaction handling:
    - SQLite with WAL handles concurrency at the database level
    - Short transactions are key - commit quickly
    - Rollback on any exception
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


async def check_database_connection() -> bool:
    """
    Verify database connection is working.
    Useful for health checks and startup validation.
    """
    try:
        async with AsyncSessionLocal() as session:
            if database_url.startswith("sqlite"):
                result = await session.execute("SELECT 1")
            else:
                from sqlalchemy import text
                result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False
