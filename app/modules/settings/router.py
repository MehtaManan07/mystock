"""Company Settings Router - API endpoints for company configuration"""

from fastapi import APIRouter, Depends

from app.modules.users.auth import TokenData, require_admin, require_any_role
from .service import SettingsService
from .schemas import CompanySettingsResponse, UpdateCompanySettingsDto

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/company", response_model=CompanySettingsResponse)
async def get_company_settings(
    current_user: TokenData = Depends(require_any_role)
):
    """
    Get active company settings. (Requires authentication)
    
    Returns the currently active company settings used for invoice generation
    and other company-wide configurations.
    """
    settings = await SettingsService.get_active_settings()
    return settings


@router.put("/company", response_model=CompanySettingsResponse)
async def update_company_settings(
    update_data: UpdateCompanySettingsDto,
    current_user: TokenData = Depends(require_admin)
):
    """
    Update company settings. (Admin only)
    
    Update any field of the active company settings.
    Only admin users can modify company settings.
    """
    settings = await SettingsService.update_active_settings(update_data)
    return settings
