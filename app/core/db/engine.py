"""
Database Engine Configuration for FastAPI.

Supports two backends, selected by the DB_BACKEND env var:
  - "turso"    (default) remote libSQL over HTTP
  - "postgres"           local PostgreSQL via psycopg3

Turso remains the default so that setting up Postgres does not change the
running app; the cutover is an explicit env-var flip, and the rollback is
flipping it back.

Uses synchronous SQLAlchemy with asyncio.to_thread() for async compatibility.
Thread-safe: entire session lifecycle stays in a single thread.
"""

from typing import TypeVar, Callable
import asyncio

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import config as settings

T = TypeVar('T')

DB_BACKEND = (settings.db_backend or "turso").strip().lower()


def _create_postgres_engine() -> Engine:
    if not settings.postgres_url:
        raise ValueError("DB_BACKEND is 'postgres' but POSTGRES_URL is not set")
    return create_engine(
        settings.postgres_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
        # The host is a 1 GB e2-micro with max_connections=20; keep the
        # ceiling well below that so pg_dump and psql can still connect.
        pool_size=5,
        max_overflow=5,
    )


def _create_turso_engine() -> Engine:
    # Build Turso URL: sqlite+libsql://host?secure=true
    # TURSO_DATABASE_URL contains "libsql://host", so we replace the scheme
    turso_url = (
        settings.turso_database_url.replace("libsql://", "sqlite+libsql://")
        + "?secure=true"
    )
    return create_engine(
        turso_url,
        connect_args={"auth_token": settings.turso_auth_token},
        echo=False,
        # Connection validation and pooling for Turso/libSQL HTTP streams
        pool_pre_ping=True,  # Test connections before using them
        pool_recycle=3600,   # Recycle connections after 1 hour
    )


if DB_BACKEND == "postgres":
    engine = _create_postgres_engine()
elif DB_BACKEND == "turso":
    engine = _create_turso_engine()
else:
    raise ValueError(
        f"Unknown DB_BACKEND {settings.db_backend!r}; expected 'turso' or 'postgres'"
    )

# Session factory
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


async def run_db(fn: Callable[[Session], T]) -> T:
    """
    Execute a database operation safely in a thread pool.
    
    The ENTIRE session lifecycle stays in one thread:
    - Session created in thread
    - fn() executed in thread  
    - Commit/rollback in thread
    - Session closed in thread
    
    Usage:
        async def get_user(user_id: int):
            def query(db: Session):
                return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            return await run_db(query)
    """
    def _execute():
        with SessionLocal() as session:
            try:
                result = fn(session)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
    
    return await asyncio.to_thread(_execute)


async def check_database_connection() -> bool:
    """
    Verify the configured database connection is working.
    Useful for health checks and startup validation.
    """
    try:
        def ping(db: Session):
            db.execute(text("SELECT 1"))
            return True
        return await run_db(ping)
    except Exception:
        return False
