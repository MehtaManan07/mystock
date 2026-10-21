"""
Alembic environment configuration.

Targets PostgreSQL, using POSTGRES_URL from .env.
"""

import os
from logging.config import fileConfig
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from alembic import context
from dotenv import load_dotenv

# Import your models here for autogenerate support
from app.core.db.base import Base
from app.modules.users.models import User
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog
from app.modules.contacts.models import Contact
from app.modules.transactions.models import Transaction, TransactionItem
from app.modules.payments.models import Payment
from app.modules.drafts.models import Draft
from app.modules.pdf_invoices.models import PdfInvoice, PdfInvoiceNumberReservation
from app.modules.settings.models import CompanySettings
from app.modules.gst_reports.models import GstReview
from app.modules.assistant.models import (
    AssistantThread,
    AssistantMessage,
    AssistantRun,
)

# Load .env
load_dotenv()

config = context.config

# -------------------------------
# DATABASE CONFIGURATION
# -------------------------------
# Postgres is the only backend; the URL comes from .env.
db_url = os.getenv("POSTGRES_URL")
if not db_url:
    raise ValueError("POSTGRES_URL is not set in .env")

config.set_main_option("sqlalchemy.url", db_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


# -------------------------------
# RUN MIGRATIONS OFFLINE
# -------------------------------
def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# -------------------------------
# RUN MIGRATIONS ONLINE
# -------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Run migrations on the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        db_url,
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


# -------------------------------
# EXECUTION
# -------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
