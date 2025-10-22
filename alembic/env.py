# from logging.config import fileConfig
# import os
# import sys
# from pathlib import Path

# from sqlalchemy import engine_from_config
# from sqlalchemy import pool

# from alembic import context

# # Add the project root to sys.path
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# # Import your models here for autogenerate support
# from app.core.db import Base
# from app.core.config import config as app_config

# # Import all models to ensure they're registered with Base.metadata
# from app.modules.users.models import User
# from app.modules.products.models import Product
# from app.modules.containers.models import Container
# from app.modules.container_products.models import ContainerProduct
# from app.modules.inventory_logs.models import InventoryLog

# # this is the Alembic Config object, which provides
# # access to the values within the .ini file in use.
# config = context.config

# # Override the sqlalchemy.url with the one from app config
# # Convert async URL to sync URL for Alembic
# db_url = app_config.database_url
# if db_url:
#     # Convert async drivers to sync drivers for Alembic
#     if db_url.startswith("postgresql+asyncpg://"):
#         db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
#     elif db_url.startswith("postgresql+psycopg://"):
#         db_url = db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://")

#     config.set_main_option("sqlalchemy.url", db_url)

# # Interpret the config file for Python logging.
# # This line sets up loggers basically.
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# # add your model's MetaData object here
# # for 'autogenerate' support
# target_metadata = Base.metadata

# # other values from the config, defined by the needs of env.py,
# # can be acquired:
# # my_important_option = config.get_main_option("my_important_option")
# # ... etc.


# def run_migrations_offline() -> None:
#     """Run migrations in 'offline' mode.

#     This configures the context with just a URL
#     and not an Engine, though an Engine is acceptable
#     here as well.  By skipping the Engine creation
#     we don't even need a DBAPI to be available.

#     Calls to context.execute() here emit the given string to the
#     script output.

#     """
#     url = config.get_main_option("sqlalchemy.url")
#     context.configure(
#         url=url,
#         target_metadata=target_metadata,
#         literal_binds=True,
#         dialect_opts={"paramstyle": "named"},
#     )

#     with context.begin_transaction():
#         context.run_migrations()


# def run_migrations_online() -> None:
#     """Run migrations in 'online' mode.

#     In this scenario we need to create an Engine
#     and associate a connection with the context.

#     """
#     connectable = engine_from_config(
#         config.get_section(config.config_ini_section, {}),
#         prefix="sqlalchemy.",
#         poolclass=pool.NullPool,
#     )

#     with connectable.connect() as connection:
#         context.configure(
#             connection=connection, target_metadata=target_metadata
#         )

#         with context.begin_transaction():
#             context.run_migrations()


# if context.is_offline_mode():
#     run_migrations_offline()
# else:
#     run_migrations_online()


import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
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

# Load environment variables from .env file
load_dotenv()

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url from environment variable
db_url = os.getenv("DB_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
else:
    raise RuntimeError("DB_URL environment variable not set")

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("No database URL configured")

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

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
