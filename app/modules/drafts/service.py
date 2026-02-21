"""
DraftsService - Business logic for managing transaction drafts
"""

from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from .models import Draft, DraftType
from .schemas import CreateDraftDto, UpdateDraftDto, CompleteDraftResponse, HydratedDraftItem
from app.modules.products.models import Product
from app.modules.containers.models import Container
from app.modules.container_products.models import ContainerProduct


class DraftsService:
    """
    Drafts service for managing transaction drafts.
    All methods use run_db() for thread-safe Turso operations.
    """

    @staticmethod
    async def create(user_id: int, create_dto: CreateDraftDto) -> Draft:
        """
        Create a new draft.
        
        Args:
            user_id: ID of the user creating the draft
            create_dto: DTO containing draft information
            
        Returns:
            Created draft entity
        """
        def _create(db: Session) -> Draft:
            draft = Draft(
                user_id=user_id,
                type=create_dto.type,
                name=create_dto.name,
                data=create_dto.data.model_dump(),  # Convert Pydantic model to dict
            )
            db.add(draft)
            db.flush()
            db.refresh(draft)
            return draft

        return await run_db(_create)

    @staticmethod
    async def find_all_by_user(user_id: int, draft_type: Optional[DraftType] = None) -> List[Draft]:
        """
        Get all drafts for a user, optionally filtered by type.
        
        Args:
            user_id: ID of the user
            draft_type: Optional filter by draft type
            
        Returns:
            List of drafts ordered by updated_at desc
        """
        def _find_all(db: Session) -> List[Draft]:
            query = select(Draft).where(Draft.user_id == user_id)
            
            if draft_type:
                query = query.where(Draft.type == draft_type)
            
            query = query.order_by(desc(Draft.updated_at))
            
            result = db.execute(query)
            return result.scalars().all()

        return await run_db(_find_all)

    @staticmethod
    async def find_one(user_id: int, draft_id: int) -> Draft:
        """
        Get a single draft by ID for a specific user.
        
        Args:
            user_id: ID of the user
            draft_id: ID of the draft
            
        Returns:
            Draft entity
            
        Raises:
            NotFoundError: If draft not found or doesn't belong to user
        """
        def _find_one(db: Session) -> Draft:
            query = select(Draft).where(
                Draft.id == draft_id,
                Draft.user_id == user_id
            )
            result = db.execute(query)
            draft = result.scalar_one_or_none()
            
            if not draft:
                raise NotFoundError("Draft", draft_id)
            
            return draft

        return await run_db(_find_one)

    @staticmethod
    async def update(user_id: int, draft_id: int, update_dto: UpdateDraftDto) -> Draft:
        """
        Update a draft.
        
        Args:
            user_id: ID of the user
            draft_id: ID of the draft to update
            update_dto: DTO containing fields to update
            
        Returns:
            Updated draft entity
            
        Raises:
            NotFoundError: If draft not found or doesn't belong to user
        """
        def _update(db: Session) -> Draft:
            query = select(Draft).where(
                Draft.id == draft_id,
                Draft.user_id == user_id
            )
            result = db.execute(query)
            draft = result.scalar_one_or_none()
            
            if not draft:
                raise NotFoundError("Draft", draft_id)
            
            # Update fields
            if update_dto.name is not None:
                draft.name = update_dto.name
            if update_dto.data is not None:
                draft.data = update_dto.data.model_dump()  # Convert Pydantic model to dict
            
            db.flush()
            db.refresh(draft)
            return draft

        return await run_db(_update)

    @staticmethod
    async def delete(user_id: int, draft_id: int) -> None:
        """
        Delete a draft.
        
        Args:
            user_id: ID of the user
            draft_id: ID of the draft to delete
            
        Raises:
            NotFoundError: If draft not found or doesn't belong to user
        """
        def _delete(db: Session) -> None:
            query = select(Draft).where(
                Draft.id == draft_id,
                Draft.user_id == user_id
            )
            result = db.execute(query)
            draft = result.scalar_one_or_none()
            
            if not draft:
                raise NotFoundError("Draft", draft_id)
            
            db.delete(draft)
            db.flush()

        await run_db(_delete)

    @staticmethod
    async def get_complete_draft(user_id: int, draft_id: int) -> CompleteDraftResponse:
        """
        Get a draft with hydrated products and containers.
        Optimized to batch-fetch all products and containers in single queries.
        
        Args:
            user_id: ID of the user
            draft_id: ID of the draft
            
        Returns:
            Complete draft with hydrated items
            
        Raises:
            NotFoundError: If draft not found or doesn't belong to user
        """
        def _get_complete(db: Session) -> CompleteDraftResponse:
            # Fetch the draft
            query = select(Draft).where(
                Draft.id == draft_id,
                Draft.user_id == user_id
            )
            result = db.execute(query)
            draft = result.scalar_one_or_none()
            
            if not draft:
                raise NotFoundError("Draft", draft_id)
            
            # Extract draft data
            draft_data = draft.data
            items_data = draft_data.get('items', [])
            
            # Extract unique product and container IDs
            product_ids = list(set(item['productId'] for item in items_data if 'productId' in item))
            container_ids = list(set(item['containerId'] for item in items_data if 'containerId' in item))
            
            # Batch fetch all products
            products_dict = {}
            if product_ids:
                products_query = select(Product).where(
                    Product.id.in_(product_ids),
                    Product.deleted_at.is_(None)
                )
                products_result = db.execute(products_query)
                products = products_result.scalars().all()
                
                # Calculate total quantity for each product
                for product in products:
                    total_qty_query = select(ContainerProduct.quantity).where(
                        ContainerProduct.product_id == product.id
                    )
                    qty_result = db.execute(total_qty_query)
                    quantities = qty_result.scalars().all()
                    total_quantity = sum(quantities) if quantities else 0
                    
                    products_dict[product.id] = {
                        'id': product.id,
                        'name': product.name,
                        'size': product.size,
                        'packing': product.packing,
                        'company_sku': product.company_sku,
                        'default_sale_price': product.default_sale_price,
                        'default_purchase_price': product.default_purchase_price,
                        'display_name': product.display_name,
                        'description': product.description,
                        'mrp': product.mrp,
                        'tags': product.tags,
                        'product_type': product.product_type,
                        'dimensions': product.dimensions,
                        'deleted_at': product.deleted_at,
                        'created_at': product.created_at,
                        'updated_at': product.updated_at,
                        'totalQuantity': total_quantity,
                    }
            
            # Batch fetch all containers
            containers_dict = {}
            if container_ids:
                containers_query = select(Container).where(
                    Container.id.in_(container_ids),
                    Container.deleted_at.is_(None)
                )
                containers_result = db.execute(containers_query)
                containers = containers_result.scalars().all()
                
                # Calculate product count for each container
                for container in containers:
                    product_count_query = select(ContainerProduct).where(
                        ContainerProduct.container_id == container.id
                    )
                    count_result = db.execute(product_count_query)
                    product_count = len(count_result.scalars().all())
                    
                    containers_dict[container.id] = {
                        'id': container.id,
                        'name': container.name,
                        'type': container.type.value,
                        'deleted_at': container.deleted_at,
                        'created_at': container.created_at,
                        'updated_at': container.updated_at,
                        'productCount': product_count,
                    }
            
            # Build hydrated items
            hydrated_items = []
            for item in items_data:
                product_id = item.get('productId')
                container_id = item.get('containerId')
                
                # Skip items with missing products or containers
                if product_id not in products_dict or container_id not in containers_dict:
                    continue
                
                hydrated_items.append(HydratedDraftItem(
                    productId=product_id,
                    containerId=container_id,
                    quantity=item.get('quantity', 0),
                    unitPrice=item.get('unitPrice', 0),
                    product=products_dict[product_id],
                    container=containers_dict[container_id],
                ))
            
            # Build complete response
            return CompleteDraftResponse(
                id=draft.id,
                user_id=draft.user_id,
                type=draft.type.value,
                name=draft.name,
                created_at=draft.created_at,
                updated_at=draft.updated_at,
                items=hydrated_items,
                transactionDate=draft_data.get('transactionDate', ''),
                contactId=draft_data.get('contactId'),
                taxPercent=draft_data.get('taxPercent', 0),
                discountAmount=draft_data.get('discountAmount', 0),
                paidAmount=draft_data.get('paidAmount', 0),
                paymentMethod=draft_data.get('paymentMethod'),
                paymentReference=draft_data.get('paymentReference'),
                notes=draft_data.get('notes'),
            )
        
        return await run_db(_get_complete)
