"""
Dashboard Router - FastAPI endpoint for aggregated dashboard data.
"""

from fastapi import APIRouter

from .service import DashboardService
from .schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard():
    """
    Get all dashboard data in a single API call.
    
    Returns:
        - stats: Basic counts (products, containers, contacts, inventory)
        - financial_overview: Total income, expenses, net balance
        - recent_transactions: Last 5 transactions
        - outstanding_contacts: Top 5 contacts with non-zero balance
    """
    return await DashboardService.get_dashboard_data()
