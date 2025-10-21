# Makefile for FastAPI + Alembic project

help:
	@echo "Usage:"
	@echo "  make run             - Run the FastAPI server"
	@echo "  make migrate         - Apply Alembic migrations"
	@echo "  make makemigration msg='message' - Create migration"
	@echo "  make expose          - Expose the FastAPI server to the internet"
	@echo "  make down            - Stop the FastAPI server"
	@echo "  make module name='module_name' - Create a new module with standard structure"
	@echo "  make celery          - Run Celery worker for scheduled tasks"


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