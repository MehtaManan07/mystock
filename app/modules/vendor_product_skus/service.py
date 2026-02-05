"""Vendor Product SKU service for managing vendor-specific SKU mappings."""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, select
from typing import Optional, List
from fastapi import HTTPException, status

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from app.modules.vendor_product_skus.models import VendorProductSku
from app.modules.vendor_product_skus.schemas import (
    CreateVendorSkuDto,
    UpdateVendorSkuDto,
    VendorSkuDetailResponse,
)
from app.modules.products.models import Product
from app.modules.contacts.models import Contact


class VendorSkuService:
    """Service for managing vendor SKU mappings using run_db pattern."""

    @staticmethod
    async def create_vendor_sku(dto: CreateVendorSkuDto) -> VendorProductSku:
        """Create a new vendor SKU mapping."""
        def _create(db: Session) -> VendorProductSku:
            # Check if product exists
            product = db.query(Product).filter(Product.id == dto.product_id).first()
            if not product:
                raise NotFoundError("Product", dto.product_id)

            # Check if vendor exists
            vendor = db.query(Contact).filter(Contact.id == dto.vendor_id).first()
            if not vendor:
                raise NotFoundError("Contact", dto.vendor_id)

            # Check if mapping already exists
            existing = db.query(VendorProductSku).filter(
                and_(
                    VendorProductSku.product_id == dto.product_id,
                    VendorProductSku.vendor_id == dto.vendor_id,
                    VendorProductSku.deleted_at.is_(None),
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vendor SKU mapping already exists for product {dto.product_id} and vendor {dto.vendor_id}",
                )

            # Create new mapping
            vendor_sku_mapping = VendorProductSku(
                product_id=dto.product_id,
                vendor_id=dto.vendor_id,
                vendor_sku=dto.vendor_sku,
            )
            db.add(vendor_sku_mapping)
            db.flush()
            db.refresh(vendor_sku_mapping)
            return vendor_sku_mapping
        
        return await run_db(_create)

    @staticmethod
    async def update_vendor_sku(
        product_id: int, vendor_id: int, dto: UpdateVendorSkuDto
    ) -> VendorProductSku:
        """Update an existing vendor SKU mapping."""
        def _update(db: Session) -> VendorProductSku:
            vendor_sku_mapping = db.query(VendorProductSku).filter(
                and_(
                    VendorProductSku.product_id == product_id,
                    VendorProductSku.vendor_id == vendor_id,
                    VendorProductSku.deleted_at.is_(None),
                )
            ).first()

            if not vendor_sku_mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Vendor SKU mapping not found for product {product_id} and vendor {vendor_id}",
                )

            vendor_sku_mapping.vendor_sku = dto.vendor_sku
            db.flush()
            db.refresh(vendor_sku_mapping)
            return vendor_sku_mapping
        
        return await run_db(_update)

    @staticmethod
    async def get_vendor_skus_for_product(product_id: int) -> List[VendorSkuDetailResponse]:
        """Get all vendor SKU mappings for a product."""
        def _get_all(db: Session) -> List[VendorSkuDetailResponse]:
            vendor_skus = (
                db.query(VendorProductSku)
                .options(joinedload(VendorProductSku.vendor))
                .filter(
                    and_(
                        VendorProductSku.product_id == product_id,
                        VendorProductSku.deleted_at.is_(None),
                    )
                )
                .all()
            )

            return [
                VendorSkuDetailResponse(
                    id=vs.id,
                    product_id=vs.product_id,
                    vendor_id=vs.vendor_id,
                    vendor_name=vs.vendor.name,
                    vendor_sku=vs.vendor_sku,
                    created_at=vs.created_at,
                    updated_at=vs.updated_at,
                )
                for vs in vendor_skus
            ]
        
        return await run_db(_get_all)

    @staticmethod
    async def get_vendor_sku(product_id: int, vendor_id: int) -> Optional[str]:
        """
        Get vendor SKU for a specific product-vendor combination.
        Returns vendor SKU if mapping exists, otherwise returns company SKU, otherwise None.
        """
        def _get(db: Session) -> Optional[str]:
            # Try to get vendor-specific SKU
            vendor_sku_mapping = db.query(VendorProductSku).filter(
                and_(
                    VendorProductSku.product_id == product_id,
                    VendorProductSku.vendor_id == vendor_id,
                    VendorProductSku.deleted_at.is_(None),
                )
            ).first()

            if vendor_sku_mapping:
                return vendor_sku_mapping.vendor_sku

            # Fallback to company SKU
            product = db.query(Product).filter(Product.id == product_id).first()
            if product and product.company_sku:
                return product.company_sku

            return None
        
        return await run_db(_get)

    @staticmethod
    async def delete_vendor_sku(product_id: int, vendor_id: int) -> None:
        """Delete (soft delete) a vendor SKU mapping."""
        def _delete(db: Session) -> None:
            vendor_sku_mapping = db.query(VendorProductSku).filter(
                and_(
                    VendorProductSku.product_id == product_id,
                    VendorProductSku.vendor_id == vendor_id,
                    VendorProductSku.deleted_at.is_(None),
                )
            ).first()

            if not vendor_sku_mapping:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Vendor SKU mapping not found for product {product_id} and vendor {vendor_id}",
                )

            # Soft delete
            from datetime import datetime
            vendor_sku_mapping.deleted_at = datetime.utcnow()
            db.flush()
        
        return await run_db(_delete)
