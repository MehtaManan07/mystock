"""
Dashboard Router - FastAPI endpoint for aggregated dashboard data.
"""

from fastapi import APIRouter, Depends

from app.modules.users.auth import TokenData, require_any_role

from .service import DashboardService
from .schemas import DashboardPeriod, DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    period: DashboardPeriod = DashboardPeriod.month,
    current_user: TokenData = Depends(require_any_role),
):
    """Period performance plus current balances, open bills, and stock.

    Period comparisons use the immediately preceding, equally long date window.
    Current balances and open bills are not restricted by the selected period.
    Standalone PDF bills are intentionally excluded from accounting metrics.
    """
    return await DashboardService.get_dashboard_data(period)
