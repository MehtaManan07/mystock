"""
Dashboard DTOs (Data Transfer Objects)
"""

from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from decimal import Decimal


class DashboardStatsResponse(BaseModel):
    """Basic statistics for dashboard"""
    
    total_products: int = Field(..., description="Total number of products")
    total_containers: int = Field(..., description="Total number of containers")
    total_contacts: int = Field(..., description="Total number of contacts")
    total_inventory: int = Field(..., description="Total inventory quantity across all containers")
    
    class Config:
        from_attributes = True


class DashboardFinancialOverviewResponse(BaseModel):
    """Financial overview for dashboard"""
    
    total_income: Decimal = Field(..., description="Total income/earnings")
    total_expenses: Decimal = Field(..., description="Total expenses/spends")
    net_balance: Decimal = Field(..., description="Net balance (income - expenses)")
    
    class Config:
        from_attributes = True


class DashboardTransactionResponse(BaseModel):
    """Simplified transaction data for dashboard"""
    
    id: int
    transaction_number: str
    type: str
    payment_status: str
    total_amount: Decimal
    transaction_date: datetime
    contact: dict | None = Field(None, description="Contact info (id, name)")
    
    class Config:
        from_attributes = True


class DashboardContactResponse(BaseModel):
    """Simplified contact data for dashboard (outstanding balances)"""
    
    id: int
    name: str
    type: str
    balance: Decimal
    
    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    """Complete dashboard data response"""
    
    stats: DashboardStatsResponse
    financial_overview: DashboardFinancialOverviewResponse
    recent_transactions: List[DashboardTransactionResponse]
    outstanding_contacts: List[DashboardContactResponse]
    
    class Config:
        from_attributes = True
