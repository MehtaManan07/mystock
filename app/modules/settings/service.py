"""Company Settings Service"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from .models import CompanySettings
from .schemas import UpdateCompanySettingsDto


class SettingsService:
    """Service for managing company settings"""

    @staticmethod
    async def get_active_settings() -> CompanySettings:
        """
        Get the active company settings.
        
        Returns:
            CompanySettings: The active company settings
            
        Raises:
            NotFoundError: If no active settings found
        """
        def _get_active(db: Session) -> CompanySettings:
            query = select(CompanySettings).where(
                CompanySettings.is_active == True,
                CompanySettings.deleted_at.is_(None)
            ).limit(1)
            
            result = db.execute(query)
            settings = result.scalar_one_or_none()
            
            if not settings:
                raise NotFoundError("CompanySettings", "active")
            
            return settings
        
        return await run_db(_get_active)

    @staticmethod
    async def update_active_settings(
        update_data: UpdateCompanySettingsDto
    ) -> CompanySettings:
        """
        Update the active company settings.
        
        Args:
            update_data: DTO with fields to update
            
        Returns:
            CompanySettings: Updated settings
            
        Raises:
            NotFoundError: If no active settings found
        """
        def _update(db: Session) -> CompanySettings:
            # Get active settings
            query = select(CompanySettings).where(
                CompanySettings.is_active == True,
                CompanySettings.deleted_at.is_(None)
            ).limit(1)
            
            result = db.execute(query)
            settings = result.scalar_one_or_none()
            
            if not settings:
                raise NotFoundError("CompanySettings", "active")
            
            # Update fields if provided
            update_dict = update_data.model_dump(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(settings, field, value)
            
            db.flush()
            db.refresh(settings)
            
            return settings
        
        return await run_db(_update)

    @staticmethod
    async def create_default_settings() -> CompanySettings:
        """
        Create default company settings if none exist.
        Used during initial setup or migrations.
        
        Returns:
            CompanySettings: Newly created settings
        """
        def _create(db: Session) -> CompanySettings:
            # Check if active settings already exist
            query = select(CompanySettings).where(
                CompanySettings.is_active == True,
                CompanySettings.deleted_at.is_(None)
            ).limit(1)
            
            result = db.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                return existing
            
            # Create new settings with defaults (defined in model)
            settings = CompanySettings(is_active=True)
            db.add(settings)
            db.flush()
            db.refresh(settings)
            
            return settings
        
        return await run_db(_create)
