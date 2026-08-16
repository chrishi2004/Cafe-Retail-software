from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import raise_forbidden
from app.core.scope import ScopeContext
from app.models import (
    BusinessType,
    CafeOrder,
    CafeOrderItem,
    CafeOrderSource,
    CafeOrderStatus,
    CafeTable,
    Company,
    Invoice,
    InvoicePayment,
    InvoicePaymentStatus,
    InvoiceStatus,
    MenuItem,
    PaymentMode,
    TableSession,
    TableSessionStatus,
)
from app.schemas.p9 import (
    P9ConsolidatedRead,
    P9DashboardFilters,
    P9DashboardRead,
    P9KpiRead,
    P9TableTurnoverRead,
    P9TopItemRead,
    P9VentureSummaryRead,
)

CAFE_SOURCE_TYPES = {"cafe_table_session", "cafe_takeaway"}
CANCELLED_STATUSES = {InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED}
REVENUE_STATUSES = {
    InvoiceStatus.ISSUED,
    InvoiceStatus.PAID,
    InvoiceStatus.PARTIAL_PAID,
    InvoiceStatus.CREDIT,
}


@dataclass(frozen=True)
class P9Period:
    start: date
    end: date


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _period(filters: P9DashboardFilters) -> P9Period:
    end = filters.end_date or datetime.now(UTC).date()
    start = filters.start_date or (end - timedelta(days=29))
    if start > end:
        start, end = end, start
    return P9Period(start, end)


def _bounds(period: P9Period) -> tuple[datetime, datetime]:
    return (
        datetime.combine(period.start, time.min, tzinfo=UTC),
        datetime.combine(period.end + timedelta(days=1), time.min, tzinfo=UTC),
    )


def _company_ids(db: Session, scope: ScopeContext) -> list[int]:
    if scope.all_companies:
        return list(
            db.scalars(
                select(Company.id).where(
                    Company.business_group_id == scope.business_group_id,
                    Company.is_active.is_(True),
                )
            )
        )
    return [scope.company_id] if scope.company_id is not None else []


def _validate_branch(scope: ScopeContext, branch_id: int | None) -> None:
    if branch_id is not None and scope.branch_ids and branch_id not in scope.branch_ids:
        raise_forbidden("The selected branch is outside your assigned scope.")


def _apply_scope(statement, model, scope: ScopeContext, filters: P9DashboardFilters):
    ids = _company_ids_from_scope(model, scope)
    statement = statement.where(model.company_id.in_(ids))
    if scope.branch_ids:
        statement = statement.where(model.branch_id.in_(scope.branch_ids))
    if filters.branch_id is not None:
        _validate_branch(scope, filters.branch_id)
        statement = statement.where(model.branch_id == filters.branch_id)
    return statement


def _company_ids_from_scope(model, scope: ScopeContext):
    # The concrete ids are injected by callers; this marker is replaced in
    # _scope_statement so SQLAlchemy never receives an unbound scope object.
    return [scope.company_id] if scope.company_id is not None else []


def _scope_statement(statement, model, scope: ScopeContext, filters: P9DashboardFilters, company_ids: list[int]):
    statement = statement.where(model.company_id.in_(company_ids))
    if scope.branch_ids:
        statement = statement.where(model.branch_id.in_(scope.branch_ids))
    if filters.branch_id is not None:
        _validate_branch(scope, filters.branch_id)
        statement = statement.where(model.branch_id == filters.branch_id)
    return statement


def _load_orders(db: Session, scope: ScopeContext, filters: P9DashboardFilters, period: P9Period) -> list[CafeOrder]:
    start, end = _bounds(period)
    statement = select(CafeOrder).where(CafeOrder.placed_at >= start, CafeOrder.placed_at < end)
    statement = _scope_statement(statement, CafeOrder, scope, filters, _company_ids(db, scope))
    if filters.source_channel:
        statement = statement.where(CafeOrder.source_channel == filters.source_channel)
    if filters.status:
        statement = statement.where(CafeOrder.status == filters.status)
    return list(db.scalars(statement))


def _load_invoices(db: Session, scope: ScopeContext, filters: P9DashboardFilters, period: P9Period, cafe_only: bool | None):
    start, end = _bounds(period)
    statement = select(Invoice).where(Invoice.invoice_date >= start, Invoice.invoice_date < end)
    statement = _scope_statement(statement, Invoice, scope, filters, _company_ids(db, scope))
    if cafe_only is True:
        statement = statement.where(Invoice.source_type.in_(CAFE_SOURCE_TYPES))
    elif cafe_only is False:
        statement = statement.where(
            (Invoice.source_type.is_(None)) | (~Invoice.source_type.in_(CAFE_SOURCE_TYPES))
        )
    if filters.status:
        statement = statement.where(Invoice.status == filters.status)
    if filters.payment_mode:
        statement = (
            statement.join(InvoicePayment)
            .join(PaymentMode, InvoicePayment.payment_mode_id == PaymentMode.id)
            .where(PaymentMode.mode_type == filters.payment_mode)
        )
    return list(db.scalars(statement).unique())


def _payment_totals(db: Session, scope: ScopeContext, filters: P9DashboardFilters, period: P9Period, cafe_only: bool | None):
    invoices = _load_invoices(db, scope, filters, period, cafe_only)
    invoice_ids = [invoice.id for invoice in invoices if invoice.status in REVENUE_STATUSES]
    if not invoice_ids:
        return Decimal("0.00"), {}
    payments = list(
        db.scalars(
            select(InvoicePayment)
            .where(InvoicePayment.invoice_id.in_(invoice_ids))
        )
    )
    total = Decimal("0.00")
    by_mode: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for payment in payments:
        if payment.is_credit_marker:
            continue
        amount = payment.amount or Decimal("0.00")
        total += amount
        mode = payment.payment_mode.mode_type.value if payment.payment_mode else "unknown"
        by_mode[mode] += amount
    return _money(total), {key: _money(value) for key, value in by_mode.items()}


def _invoice_metrics(invoices: Iterable[Invoice]) -> tuple[Decimal, Decimal, Decimal]:
    billed = Decimal("0.00")
    net = Decimal("0.00")
    outstanding = Decimal("0.00")
    for invoice in invoices:
        if invoice.status in REVENUE_STATUSES:
            value = invoice.grand_total or Decimal("0.00")
            billed += value
            net += value
            outstanding += invoice.balance_due or Decimal("0.00")
        elif invoice.status in CANCELLED_STATUSES:
            # Cancelled/returned invoices are excluded from billed revenue and
            # therefore cannot be counted twice by a linked Sale.
            continue
    return _money(billed), _money(net), _money(outstanding)


def _cafe_dashboard(db: Session, scope: ScopeContext, filters: P9DashboardFilters) -> P9DashboardRead:
    period = _period(filters)
    orders = _load_orders(db, scope, filters, period)
    if not orders and scope.company_id is None and scope.role.value != "super_admin":
        raise_forbidden("A venture scope is required for Cafe reporting.")
    invoices = _load_invoices(db, scope, filters, period, True)
    billed, net, outstanding = _invoice_metrics(invoices)
    collections, payment_mix = _payment_totals(db, scope, filters, period, True)
    ordered_value = sum(
        (order.estimated_total or Decimal("0.00") for order in orders),
        Decimal("0.00"),
    )
    cancelled_value = sum(
        (order.estimated_total or Decimal("0.00") for order in orders)
        if order.status == CafeOrderStatus.CANCELLED and order.billed_invoice_id is None
        else Decimal("0.00")
        for order in orders
    )
    eligible_orders = [order for order in orders if order.status not in {CafeOrderStatus.REJECTED, CafeOrderStatus.CANCELLED}]
    average_bill = billed / len(invoices) if invoices else Decimal("0.00")
    open_sessions = len(
        db.scalars(
            _scope_statement(
                select(TableSession).where(
                    TableSession.status.in_(
                        [TableSessionStatus.OPEN, TableSessionStatus.BILL_REQUESTED, TableSessionStatus.BILLED]
                    )
                ),
                TableSession,
                scope,
                filters,
                _company_ids(db, scope),
            )
        ).all()
    )
    top_items: dict[int, dict[str, object]] = {}
    item_statement = (
        select(CafeOrderItem)
        .join(CafeOrder, CafeOrder.id == CafeOrderItem.cafe_order_id)
        .where(CafeOrder.placed_at >= _bounds(period)[0], CafeOrder.placed_at < _bounds(period)[1])
    )
    item_statement = _scope_statement(item_statement, CafeOrderItem, scope, filters, _company_ids(db, scope))
    for item in db.scalars(item_statement):
        if item.cafe_order_id and item.item_status in {"cancelled", "rejected"}:
            continue
        bucket = top_items.setdefault(
            item.menu_item_id,
            {"item_name": item.menu_item_name_snapshot, "units": Decimal("0.00"), "value": Decimal("0.00")},
        )
        bucket["units"] += Decimal(item.quantity)
        bucket["value"] += item.line_total or Decimal("0.00")
    top_rows = [
        P9TopItemRead(menu_item_id=menu_id, item_name=str(row["item_name"]), units_sold=row["units"], ordered_value=_money(row["value"]))
        for menu_id, row in sorted(top_items.items(), key=lambda pair: (pair[1]["value"], pair[1]["units"]), reverse=True)[:10]
    ]
    source_mix: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for order in eligible_orders:
        source_mix[order.source_channel.value] += order.estimated_total or Decimal("0.00")
    sessions = list(
        db.scalars(
            _scope_statement(
                select(TableSession).where(
                    TableSession.opened_at >= _bounds(period)[0],
                    TableSession.opened_at < _bounds(period)[1],
                ),
                TableSession,
                scope,
                filters,
                _company_ids(db, scope),
            )
        )
    )
    durations = [
        (session.closed_at - session.opened_at).total_seconds() / 60
        for session in sessions
        if session.closed_at is not None
    ]
    return P9DashboardRead(
        scope="cafe",
        venture="cafe",
        period_start=period.start,
        period_end=period.end,
        kpis=P9KpiRead(
            order_count=len(eligible_orders),
            ordered_value=_money(ordered_value),
            billed_revenue=billed,
            net_billed_revenue=net,
            collections=collections,
            outstanding=outstanding,
            cancelled_value=_money(cancelled_value),
            average_bill_value=_money(average_bill),
            open_unbilled_sessions=open_sessions,
        ),
        top_items=top_rows,
        source_channel_mix={key: _money(value) for key, value in source_mix.items()},
        payment_mode_mix=payment_mix,
        table_turnover=P9TableTurnoverRead(
            session_count=len(sessions),
            closed_session_count=sum(1 for session in sessions if session.closed_at is not None),
            average_duration_minutes=_money(Decimal(str(sum(durations) / len(durations))) if durations else None),
        ),
    )


def get_cafe_dashboard(db: Session, *, scope: ScopeContext, filters: P9DashboardFilters) -> P9DashboardRead:
    return _cafe_dashboard(db, scope, filters)


def _summary_for_company(db: Session, company: Company, scope: ScopeContext, filters: P9DashboardFilters) -> P9VentureSummaryRead:
    company_scope = ScopeContext(
        user_id=scope.user_id,
        role=scope.role,
        business_group_id=scope.business_group_id,
        company_id=company.id,
        all_companies=False,
        branch_ids=scope.branch_ids,
        permissions=scope.permissions,
    )
    invoices = _load_invoices(db, company_scope, filters, _period(filters), None)
    billed, net, outstanding = _invoice_metrics(invoices)
    collections, _ = _payment_totals(db, company_scope, filters, _period(filters), None)
    return P9VentureSummaryRead(
        company_id=company.id,
        venture=company.business_type.value,
        company_name=company.trade_name or company.name,
        billed_revenue=billed,
        net_billed_revenue=net,
        collections=collections,
        outstanding=outstanding,
    )


def get_consolidated_dashboard(db: Session, *, scope: ScopeContext, filters: P9DashboardFilters) -> P9ConsolidatedRead:
    period = _period(filters)
    companies = list(
        db.scalars(
            select(Company).where(
                Company.id.in_(_company_ids(db, scope)),
                Company.business_group_id == scope.business_group_id,
                Company.is_active.is_(True),
            )
        )
    )
    summaries = [_summary_for_company(db, company, scope, filters) for company in companies]
    billed = sum((row.billed_revenue for row in summaries), Decimal("0.00"))
    net = sum((row.net_billed_revenue for row in summaries), Decimal("0.00"))
    collections = sum((row.collections for row in summaries), Decimal("0.00"))
    outstanding = sum((row.outstanding for row in summaries), Decimal("0.00"))
    return P9ConsolidatedRead(
        scope="all_ventures" if scope.all_companies else "venture",
        venture="all",
        period_start=period.start,
        period_end=period.end,
        kpis=P9KpiRead(
            billed_revenue=_money(billed),
            net_billed_revenue=_money(net),
            collections=_money(collections),
            outstanding=_money(outstanding),
        ),
        venture_summaries=summaries,
    )


def export_cafe_csv(db: Session, *, scope: ScopeContext, filters: P9DashboardFilters) -> str:
    dashboard = get_cafe_dashboard(db, scope=scope, filters=filters)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["venture", "branch_id", "period_start", "period_end", "metric", "value"])
    for key in ("order_count", "ordered_value", "billed_revenue", "net_billed_revenue", "collections", "outstanding", "cancelled_value", "average_bill_value", "open_unbilled_sessions"):
        writer.writerow(["cafe", filters.branch_id or "all", dashboard.period_start, dashboard.period_end, key, getattr(dashboard.kpis, key)])
    return output.getvalue()


def export_consolidated_csv(db: Session, *, scope: ScopeContext, filters: P9DashboardFilters) -> str:
    dashboard = get_consolidated_dashboard(db, scope=scope, filters=filters)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["venture", "company_id", "company_name", "billed_revenue", "net_billed_revenue", "collections", "outstanding"])
    for row in dashboard.venture_summaries:
        writer.writerow([row.venture, row.company_id, row.company_name, row.billed_revenue, row.net_billed_revenue, row.collections, row.outstanding])
    return output.getvalue()


def cafe_ai_tool(db: Session, *, scope: ScopeContext, question: str) -> tuple[str, str, dict]:
    dashboard = get_cafe_dashboard(db, scope=scope, filters=P9DashboardFilters())
    lowered = question.lower()
    if "table" in lowered or "open" in lowered:
        return "get_open_table_sessions", "Open Cafe table sessions for the current scope.", {"scope": dashboard.scope, "open_unbilled_sessions": dashboard.kpis.open_unbilled_sessions}
    if "top" in lowered or "most" in lowered:
        return "get_cafe_top_items", "Top Cafe menu items for the current scope.", {"scope": dashboard.scope, "items": [row.model_dump() for row in dashboard.top_items]}
    if "cancel" in lowered:
        return "get_cafe_cancelled_items", "Cancelled, unbilled Cafe order value for the current scope.", {"scope": dashboard.scope, "cancelled_value": dashboard.kpis.cancelled_value}
    if "collect" in lowered or "payment" in lowered:
        return "get_cafe_payment_reconciliation", "Recorded Cafe invoice payments for the current scope.", {"scope": dashboard.scope, "collections": dashboard.kpis.collections, "payment_mode_mix": dashboard.payment_mode_mix}
    if "compare" in lowered or "retail" in lowered:
        if scope.role.value != "super_admin":
            return "cafe_scope_denied", "Cafe AI cannot compare or disclose Retail data.", {"scope": dashboard.scope, "allowed": False}
        consolidated = get_consolidated_dashboard(db, scope=scope, filters=P9DashboardFilters())
        return "get_venture_comparison", "Super Admin-only venture comparison.", {"scope": consolidated.scope, "ventures": [row.model_dump() for row in consolidated.venture_summaries]}
    return "get_cafe_sales_summary", "Cafe billed, collected, outstanding, and ordered metrics.", {"scope": dashboard.scope, "kpis": dashboard.kpis.model_dump()}
