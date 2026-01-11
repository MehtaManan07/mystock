# Makefile for FastAPI + Alembic project

# Use zsh so personal aliases work
SHELL := /bin/zsh

help:
	@echo "Usage:"
	@echo "  make run             - Run the FastAPI server"
	@echo "  make migrate         - Apply Alembic migrations"
	@echo "  make makemigration msg='message' - Create migration"
	@echo "  make downgrade       - Rollback one migration"
	@echo "  make dbversion       - Show current migration version"
	@echo "  make expose          - Expose the FastAPI server to the internet"
	@echo "  make module name='module_name' - Create a new module with standard structure"
	@echo "  make celery          - Run Celery worker for scheduled tasks"
	@echo ""
	@echo "SQLite Management:"
	@echo "  make backup          - Create a timestamped SQLite backup"
	@echo "  make restore file='path' - Restore from a backup file"
	@echo "  make db-shell        - Open SQLite CLI"
	@echo "  make db-vacuum       - Optimize SQLite database"
	@echo "  make db-info         - Show database file info"
	@echo "  make migrate-fresh   - Reset DB and run migrations (DESTRUCTIVE!)"
	@echo ""
	@echo "Data Migration (PostgreSQL to SQLite):"
	@echo "  make migrate-from-pg-dry  - Test migration without changes"
	@echo "  make migrate-from-pg      - Migrate data from PostgreSQL"
	@echo "  make migrate-from-pg-clear - Clear SQLite and migrate from PostgreSQL"


# Configs
APP_MODULE=app.main:app
HOST=127.0.0.1
PORT=8000
ALEMBIC=alembic
ALEMBIC_CONFIG=alembic.ini

# Run FastAPI server
run:
	uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

# Alembic commands
migrate:
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) upgrade head

# Create Alembic revision with a custom message: make makemigration msg="your message"
makemigration:
ifndef msg
	$(error You must provide a message using msg="your message")
endif
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) revision --autogenerate -m "$(msg)"


downgrade:
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) downgrade -1

# Show Alembic current version
dbversion:
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) current

# Clean __pycache__ and .pyc files
clean:
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.pyc' -delete

# Run Celery worker for scheduled tasks
celery:
	celery -A app.celery_app worker --loglevel=info --pool=solo

# Create a new module with standard structure: make module name="module_name"
module:
ifndef name
	$(error You must provide a module name using name="module_name")
endif
	$(eval CLASS_NAME := $(shell echo $(name) | perl -pe 's/(^|_)(.)/\U$$2/g'))
	@echo "Creating module: $(name)"
	@mkdir -p app/modules/$(name)
	@echo "# $(name) module" > app/modules/$(name)/__init__.py
	@echo "from pydantic import BaseModel\nfrom typing import Optional\nfrom datetime import datetime\n\n\nclass Create$(CLASS_NAME)Dto(BaseModel):\n    pass\n\n\nclass Update$(CLASS_NAME)Dto(BaseModel):\n    pass\n\n\nclass $(CLASS_NAME)ResponseDto(BaseModel):\n    id: int\n    created_at: datetime\n    updated_at: Optional[datetime] = None\n\n    class Config:\n        from_attributes = True\n" > app/modules/$(name)/dto.py
	@echo "from __future__ import annotations\nfrom datetime import datetime\nfrom sqlalchemy import String, Integer, DateTime\nfrom sqlalchemy.orm import Mapped, mapped_column\nfrom typing import Optional\n\nfrom app.core.db.base import BaseModel\n\n\nclass $(CLASS_NAME)(BaseModel):\n    \"\"\"$(CLASS_NAME) model\"\"\"\n\n    __tablename__ = \"$(name)\"\n\n    # Add your columns here\n\n    def __repr__(self) -> str:\n        return f\"<$(CLASS_NAME)(id={self.id})>\"\n" > app/modules/$(name)/models.py
	@echo "import logging\nfrom sqlalchemy.ext.asyncio import AsyncSession\nfrom sqlalchemy import select\nfrom typing import Optional, List\n\nfrom app.core.db import $(CLASS_NAME)\nfrom app.modules.$(name).dto import Create$(CLASS_NAME)Dto, Update$(CLASS_NAME)Dto\n\nlogger = logging.getLogger(__name__)\n\n\nclass $(CLASS_NAME)Service:\n    def __init__(self):\n        self.logger = logger\n\n    async def create(self, db: AsyncSession, data: Create$(CLASS_NAME)Dto):\n        \"\"\"Create a new $(name)\"\"\"\n        # TODO: Implement create logic\n        pass\n\n    async def get_by_id(self, db: AsyncSession, id: int):\n        \"\"\"Get $(name) by ID\"\"\"\n        result = await db.execute(select($(CLASS_NAME)).where($(CLASS_NAME).id == id))\n        return result.scalar_one_or_none()\n\n\n# Global service instance\n$(name)_service = $(CLASS_NAME)Service()\n" > app/modules/$(name)/service.py
	@echo "from fastapi import APIRouter\nfrom typing import List\n\nfrom app.core.dependencies import DatabaseDep\nfrom app.modules.$(name).dto import Create$(CLASS_NAME)Dto, Update$(CLASS_NAME)Dto, $(CLASS_NAME)ResponseDto\n\nrouter = APIRouter(prefix=\"/$(name)\", tags=[\"$(name)\"])\n\n\n@router.get(\"/\")\nasync def get_all(\n    db: DatabaseDep,\n):\n    \"\"\"Get all $(name)\"\"\"\n    # TODO: Implement endpoint\n    return {\"message\": \"Not implemented\"}\n" > app/modules/$(name)/controller.py
	@echo "from typing import TypedDict\n\n# Add your custom types here\n" > app/modules/$(name)/types.py
	@echo "✅ Module '$(name)' created successfully!"
	@echo "📁 Location: app/modules/$(name)/"
	@echo "📝 Next steps:"
	@echo "   1. Define your model in models.py"
	@echo "   2. Update DTOs in dto.py"
	@echo "   3. Implement service methods in service.py"
	@echo "   4. Add routes in controller.py"
	@echo "   5. Register the router in app/main.py"

expose:
	ssh -p 443 -R0:localhost:8000 qr@free.pinggy.io

commit:
ifndef msg
	$(error You must provide a message using msg="your message")
endif
	@zsh -i -c 'pgit add .'
	@zsh -i -c 'pgit commit -m "$(msg)"'


start-client:
	cd frontend && npm run dev

# =============================================================================
# SQLite Management Commands
# =============================================================================

# Database paths
DB_FILE=data/inventory.db
BACKUP_DIR=backups

# Create a timestamped backup using SQLite backup API
backup:
	@mkdir -p $(BACKUP_DIR)
	@if [ -f $(DB_FILE) ]; then \
		TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
		BACKUP_FILE=$(BACKUP_DIR)/inventory_backup_$${TIMESTAMP}.db; \
		echo "Creating backup: $${BACKUP_FILE}"; \
		sqlite3 $(DB_FILE) ".backup $${BACKUP_FILE}"; \
		echo "Backup created successfully!"; \
		ls -lh $${BACKUP_FILE}; \
	else \
		echo "Database not found: $(DB_FILE)"; \
		exit 1; \
	fi

# Restore from a backup file
restore:
ifndef file
	$(error You must provide a backup file using file="path/to/backup.db")
endif
	@if [ ! -f $(file) ]; then \
		echo "Backup file not found: $(file)"; \
		exit 1; \
	fi
	@if [ -f $(DB_FILE) ]; then \
		echo "Creating pre-restore backup..."; \
		cp $(DB_FILE) $(DB_FILE).pre_restore; \
	fi
	@echo "Restoring from $(file)..."
	@sqlite3 $(file) ".backup $(DB_FILE)"
	@rm -f $(DB_FILE)-wal $(DB_FILE)-shm
	@echo "Restore complete!"

# Open SQLite CLI for the database
db-shell:
	@if [ -f $(DB_FILE) ]; then \
		sqlite3 $(DB_FILE); \
	else \
		echo "Database not found: $(DB_FILE)"; \
		echo "Run 'make migrate' first to create the database."; \
		exit 1; \
	fi

# Optimize the database (reclaim space, rebuild indexes)
db-vacuum:
	@if [ -f $(DB_FILE) ]; then \
		echo "Running VACUUM on database..."; \
		sqlite3 $(DB_FILE) "VACUUM;"; \
		echo "Running ANALYZE for query optimization..."; \
		sqlite3 $(DB_FILE) "ANALYZE;"; \
		echo "Database optimized!"; \
		ls -lh $(DB_FILE); \
	else \
		echo "Database not found: $(DB_FILE)"; \
		exit 1; \
	fi

# Show database info
db-info:
	@echo "=== Database Info ==="
	@if [ -f $(DB_FILE) ]; then \
		echo "File: $(DB_FILE)"; \
		ls -lh $(DB_FILE); \
		echo ""; \
		echo "=== PRAGMA Settings ==="; \
		sqlite3 $(DB_FILE) "PRAGMA journal_mode; PRAGMA foreign_keys; PRAGMA busy_timeout;"; \
		echo ""; \
		echo "=== Table Row Counts ==="; \
		sqlite3 $(DB_FILE) "SELECT name, (SELECT COUNT(*) FROM \"\" || name || \"\") as count FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version';"; \
	else \
		echo "Database not found: $(DB_FILE)"; \
	fi
	@echo ""
	@echo "=== WAL Files ==="
	@ls -lh $(DB_FILE)-wal $(DB_FILE)-shm 2>/dev/null || echo "No WAL files present"

# Reset database and run migrations (DESTRUCTIVE!)
migrate-fresh:
	@echo "WARNING: This will DELETE the database and all data!"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@rm -f $(DB_FILE) $(DB_FILE)-wal $(DB_FILE)-shm
	@mkdir -p data
	@echo "Running fresh migrations..."
	$(ALEMBIC) -c $(ALEMBIC_CONFIG) upgrade head
	@echo "Fresh database created!"

# List available backups
backup-list:
	@echo "=== Available Backups ==="
	@ls -lht $(BACKUP_DIR)/*.db 2>/dev/null || echo "No backups found in $(BACKUP_DIR)/"

# Clean old backups (keep last 7)
backup-clean:
	@echo "Cleaning old backups (keeping last 7)..."
	@cd $(BACKUP_DIR) && ls -t *.db 2>/dev/null | tail -n +8 | xargs -r rm -v
	@echo "Done!"

# =============================================================================
# Data Migration Commands
# =============================================================================

# Migrate data from PostgreSQL to SQLite (dry run first!)
migrate-from-pg-dry:
	@echo "Running PostgreSQL to SQLite migration (DRY RUN)..."
	@echo "This will NOT modify the SQLite database."
	python scripts/migrate_pg_to_sqlite.py --dry-run

# Migrate data from PostgreSQL to SQLite (actual migration)
migrate-from-pg:
ifndef DB_URL
	$(error DB_URL must be set to your PostgreSQL connection string)
endif
	@echo "WARNING: This will migrate all data from PostgreSQL to SQLite!"
	@echo "Make sure you have:"
	@echo "  1. Run 'make migrate' to create SQLite schema"
	@echo "  2. Backed up your PostgreSQL database"
	@echo ""
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	python scripts/migrate_pg_to_sqlite.py

# Migrate with clearing existing SQLite data
migrate-from-pg-clear:
ifndef DB_URL
	$(error DB_URL must be set to your PostgreSQL connection string)
endif
	@echo "WARNING: This will DELETE existing SQLite data and migrate from PostgreSQL!"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	python scripts/migrate_pg_to_sqlite.py --clear