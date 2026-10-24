"""
Dashboard DTOs (Data Transfer Objects)
"""

from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal


class DashboardStatsResponse(BaseModel):
    """Basic statistics for dashboard"""
    
    total_products: int = Field(..., description="Total number of products")
    total_containers: int = Field(..., description="Total number of containers")
    total_contacts: int = Field(..., description="Total number of contacts")
    total_inventory: int = Field(..., description="Total inventory quantity across all containers")
    
    class Config:
        from_attributes = True


class DashboardPeriod(str, Enum):
    month = "month"
    last_month = "last_month"
    last_90_days = "90_days"


class DashboardWindow(BaseModel):
    start: date
    end: date
    comparison_start: date
    comparison_end: date


class DashboardPerformance(BaseModel):
    sales: Decimal
    sale_count: int
    units_sold: int
    income: Decimal
    expenses: Decimal
    net_cash: Decimal


class DashboardCashDay(BaseModel):
    date: date
    income: Decimal
    expenses: Decimal


class DashboardBillContact(BaseModel):
    id: int
    name: str


class DashboardBill(BaseModel):
    id: int
    transaction_number: str
    type: Literal["sale", "purchase"]
    payment_status: Literal["paid", "partial", "unpaid"]
    transaction_date: date
    total_amount: Decimal
    balance_due: Decimal
    age_days: int
    contact: DashboardBillContact | None


class DashboardBalances(BaseModel):
    receivables: Decimal
    payables: Decimal
    receivable_accounts: int
    payable_accounts: int
    open_sales_count: int
    open_purchases_count: int
    oldest_sales: list[DashboardBill]
    oldest_purchases: list[DashboardBill]


class DashboardBestSeller(BaseModel):
    id: int
    name: str
    size: str
    packing: str
    company_sku: str | None
    units_sold: int
    stock_on_hand: int


class DashboardResponse(BaseModel):
    as_of: date
    period: DashboardPeriod
    window: DashboardWindow
    current: DashboardPerformance
    previous: DashboardPerformance
    cash_flow: list[DashboardCashDay]
    balances: DashboardBalances
    best_sellers: list[DashboardBestSeller]
    sold_products_out_of_stock: int = Field(
        ..., description="Active products sold in the selected period with current stock <= 0"
    )
    recent_transactions: list[DashboardBill]
    stats: DashboardStatsResponse
