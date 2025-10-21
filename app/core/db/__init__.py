# Import all models here to ensure they're loaded together
# This prevents circular import issues with relationships

from app.core.db.base import Base, BaseModel
from app.modules.users.models import User
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.container_products.models import ContainerProduct
from app.modules.inventory_logs.models import InventoryLog

# Export for easy importing
__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Product",
    "Container",
    "ContainerProduct",
    "InventoryLog",
]
