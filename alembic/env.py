"""
Alembic environment configuration with SQLite and PostgreSQL support.

Key features:
- Async migration support for both databases
- Batch mode for SQLite (required for ALTER TABLE operations)
- Auto-detection of database type from URL
- Proper driver conversion for Alembic (async -> sync)
"""

import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool, event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from dotenv import load_dotenv

# Import your models here so Alembic can detect them
from app.core.db.base import Base
from app.modules.users.models import User
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog
from app.modules.contacts.models import Contact
from app.modules.transactions.models import Transaction, TransactionItem
from app.modules.payments.models import Payment

# Load environment variables from .env file
load_dotenv()

# this is the Alembic Config object
config = context.config

# Get database URL from environment
db_url = os.getenv("DB_URL")

# If no DB_URL, use SQLite default
if not db_url:
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    db_url = f"sqlite+aiosqlite:///{project_root}/data/inventory.db"
    # Ensure data directory exists
    (project_root / "data").mkdir(parents=True, exist_ok=True)

config.set_main_option("sqlalchemy.url", db_url)

# Determine if we're using SQLite
is_sqlite = db_url.startswith("sqlite")

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def _configure_sqlite_connection(dbapi_connection, connection_record):
    """
    Configure SQLite connection with same settings as the app.
    Required for migrations to work correctly with foreign keys.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This generates SQL without connecting to the database.
    Useful for reviewing migration SQL before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        # Enable batch mode for SQLite - required for ALTER TABLE operations
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Configure and run migrations with the given connection.
    
    For SQLite:
    - render_as_batch=True: Required because SQLite doesn't support
      many ALTER TABLE operations. Batch mode recreates tables.
    - No naming convention issues with batch mode.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Enable batch mode for SQLite - recreates tables for ALTER operations
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.
    
    Handles both SQLite (aiosqlite) and PostgreSQL (asyncpg).
    """
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("No database URL configured")

    # Create async engine
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    # Register SQLite pragma settings
    if is_sqlite:
        @event.listens_for(connectable.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            _configure_sqlite_connection(dbapi_connection, connection_record)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
