from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class P9DashboardFilters(BaseModel):
    branch_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    source_channel: str | None = None
    status: str | None = None
    payment_mode: str | None = None
    menu_category_id: int | None = None
    menu_item_id: int | None = None
    table_id: int | None = None


class P9KpiRead(BaseModel):
    order_count: int = 0
    ordered_value: Decimal = Decimal("0.00")
    billed_revenue: Decimal = Decimal("0.00")
    net_billed_revenue: Decimal = Decimal("0.00")
    collections: Decimal = Decimal("0.00")
    outstanding: Decimal = Decimal("0.00")
    cancelled_value: Decimal = Decimal("0.00")
    void_value: Decimal = Decimal("0.00")
    average_bill_value: Decimal = Decimal("0.00")
    open_unbilled_sessions: int = 0


class P9TopItemRead(BaseModel):
    menu_item_id: int
    item_name: str
    units_sold: Decimal
    ordered_value: Decimal


class P9TableTurnoverRead(BaseModel):
    session_count: int = 0
    closed_session_count: int = 0
    average_duration_minutes: Decimal | None = None


class P9DashboardRead(BaseModel):
    scope: str
    venture: str
    period_start: date
    period_end: date
    kpis: P9KpiRead
    top_items: list[P9TopItemRead] = Field(default_factory=list)
    source_channel_mix: dict[str, Decimal] = Field(default_factory=dict)
    payment_mode_mix: dict[str, Decimal] = Field(default_factory=dict)
    table_turnover: P9TableTurnoverRead = Field(default_factory=P9TableTurnoverRead)


class P9VentureSummaryRead(BaseModel):
    company_id: int
    venture: str
    company_name: str
    billed_revenue: Decimal
    net_billed_revenue: Decimal
    collections: Decimal
    outstanding: Decimal


class P9ConsolidatedRead(P9DashboardRead):
    venture_summaries: list[P9VentureSummaryRead] = Field(default_factory=list)
