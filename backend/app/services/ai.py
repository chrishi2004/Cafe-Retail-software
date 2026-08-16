from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import BranchScope
from app.api.errors import raise_forbidden, raise_not_found
from app.core.config import settings
from app.models import (
    AIChatMessage,
    AIChatSession,
    ChatSender,
    ForecastType,
    PurchaseOrderStatus,
    User,
)
from app.schemas.ai import (
    AIChatMessageRead,
    AIChatRequest,
    AIChatResponse,
    AIChatSessionDetailRead,
    AIChatSessionRead,
    AIToolCallRead,
)
from app.schemas.forecasts import ForecastRunCreate
from app.services.dashboard import (
    DashboardFilters,
    get_inventory_dashboard,
    get_purchase_orders_dashboard,
    get_sales_dashboard,
)
from app.services.forecasting import run_forecast
from app.services.purchase_orders import PurchaseOrderFilters, query_purchase_orders
from app.services.reorder import ReorderFilters, query_reorder_recommendations

OPEN_ORDER_STATUSES = [
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.PENDING_APPROVAL,
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.ORDERED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
]
MAX_LIST_ITEMS = 5


@dataclass(frozen=True)
class AIToolResult:
    name: str
    description: str
    data: dict[str, Any]


@dataclass(frozen=True)
class IntentResult:
    intent: str
    response: str
    tool_results: list[AIToolResult]
    requires_confirmation: bool = False
    suggested_action: str | None = None


def money(value: str | Decimal | int | float | None) -> str:
    amount = Decimal(str(value or "0"))
    return f"INR {amount:,.2f}"


def quantity(value: str | Decimal | int | float | None) -> str:
    amount = Decimal(str(value or "0"))
    return f"{amount:,.2f}"


def today() -> date:
    return datetime.now(UTC).date()


def month_bounds(anchor: date) -> tuple[date, date]:
    return anchor.replace(day=1), anchor


def previous_month_bounds(anchor: date) -> tuple[date, date]:
    first_this_month = anchor.replace(day=1)
    previous_end = first_this_month - timedelta(days=1)
    return previous_end.replace(day=1), previous_end


def branch_id_for_default_scope(branch_scope: BranchScope) -> int | None:
    return None if branch_scope.all_branches else branch_scope.branch_ids[0]


def safe_data(value: Any) -> dict[str, Any]:
    encoded = jsonable_encoder(value)
    return encoded if isinstance(encoded, dict) else {"value": encoded}


def list_data(value: Any) -> list[dict[str, Any]]:
    encoded = jsonable_encoder(value)
    if not isinstance(encoded, list):
        return []
    return [row for row in encoded if isinstance(row, dict)]


def chat_message_read(message: AIChatMessage) -> AIChatMessageRead:
    return AIChatMessageRead(
        id=message.id,
        session_id=message.session_id,
        sender=message.sender,
        message=message.message,
        metadata_json=message.metadata_json,
        created_at=message.created_at,
    )


def session_read(session: AIChatSession, *, include_last_message: bool = True) -> AIChatSessionRead:
    last_message = None
    if include_last_message and session.messages:
        last_message = session.messages[-1].message
    return AIChatSessionRead(
        id=session.id,
        user_id=session.user_id,
        branch_id=session.branch_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message=last_message,
    )


def session_detail_read(session: AIChatSession) -> AIChatSessionDetailRead:
    base = session_read(session)
    return AIChatSessionDetailRead(
        **base.model_dump(),
        messages=[chat_message_read(message) for message in session.messages],
    )


def title_from_message(message: str) -> str:
    normalized = " ".join(message.strip().split())
    if len(normalized) <= 60:
        return normalized or "New chat"
    return f"{normalized[:57]}..."


def get_or_create_session(
    db: Session,
    *,
    payload: AIChatRequest,
    user: User,
) -> AIChatSession:
    if payload.session_id is not None:
        session = db.scalar(
            select(AIChatSession)
            .options(joinedload(AIChatSession.messages))
            .where(AIChatSession.id == payload.session_id)
        )
        if session is None:
            raise_not_found("AI chat session not found.")
        if session.user_id != user.id:
            raise_forbidden("You can only access your own AI chat sessions.")
        return session

    session = AIChatSession(
        user_id=user.id,
        branch_id=user.branch_id,
        title=title_from_message(payload.message),
    )
    db.add(session)
    db.flush()
    return session


def query_chat_sessions(
    db: Session,
    *,
    user: User,
    limit: int = 50,
) -> list[AIChatSessionRead]:
    statement = (
        select(AIChatSession)
        .options(joinedload(AIChatSession.messages))
        .where(AIChatSession.user_id == user.id)
        .order_by(AIChatSession.updated_at.desc(), AIChatSession.id.desc())
        .limit(max(1, min(limit, 100)))
    )
    return [session_read(session) for session in db.scalars(statement).unique().all()]


def get_chat_session_detail(
    db: Session,
    *,
    session_id: int,
    user: User,
) -> AIChatSessionDetailRead:
    session = db.scalar(
        select(AIChatSession)
        .options(joinedload(AIChatSession.messages))
        .where(AIChatSession.id == session_id)
    )
    if session is None:
        raise_not_found("AI chat session not found.")
    if session.user_id != user.id:
        raise_forbidden("You can only access your own AI chat sessions.")
    session.messages.sort(key=lambda message: (message.created_at, message.id))
    return session_detail_read(session)


def get_sales_summary(
    db: Session,
    *,
    branch_scope: BranchScope,
    start_date: date,
    end_date: date,
) -> AIToolResult:
    dashboard = get_sales_dashboard(
        db,
        branch_scope=branch_scope,
        filters=DashboardFilters(
            branch_id=branch_id_for_default_scope(branch_scope),
            start_date=start_date,
            end_date=end_date,
        ),
    )
    data = safe_data(
        {
            "period_start": dashboard.period_start,
            "period_end": dashboard.period_end,
            "summary": dashboard.summary,
            "top_products": dashboard.top_products[:MAX_LIST_ITEMS],
            "branch_performance": dashboard.branch_performance[:MAX_LIST_ITEMS],
        }
    )
    return AIToolResult(
        name="get_sales_summary",
        description="Sales revenue, profit, units, transactions, top products, and branch performance from dashboard data.",
        data=data,
    )


def get_low_stock_items(
    db: Session,
    *,
    branch_scope: BranchScope,
) -> AIToolResult:
    start_date, end_date = month_bounds(today())
    dashboard = get_inventory_dashboard(
        db,
        branch_scope=branch_scope,
        filters=DashboardFilters(
            branch_id=branch_id_for_default_scope(branch_scope),
            start_date=start_date,
            end_date=end_date,
        ),
    )
    items = list_data(dashboard.low_stock_items)
    data = {
        "count": dashboard.summary.low_stock_product_count,
        "items": items[:10],
    }
    return AIToolResult(
        name="get_low_stock_items",
        description="Products where quantity on hand is at or below reorder threshold.",
        data=safe_data(data),
    )


def get_top_products(
    db: Session,
    *,
    branch_scope: BranchScope,
) -> AIToolResult:
    start_date, end_date = month_bounds(today())
    dashboard = get_sales_dashboard(
        db,
        branch_scope=branch_scope,
        filters=DashboardFilters(
            branch_id=branch_id_for_default_scope(branch_scope),
            start_date=start_date,
            end_date=end_date,
        ),
    )
    data = safe_data(
        {
            "period_start": dashboard.period_start,
            "period_end": dashboard.period_end,
            "items": dashboard.top_products[:10],
        }
    )
    return AIToolResult(
        name="get_top_products",
        description="Top products ranked by units sold and revenue for the current month.",
        data=data,
    )


def get_slow_moving_products(
    db: Session,
    *,
    branch_scope: BranchScope,
) -> AIToolResult:
    end_date = today()
    start_date = end_date - timedelta(days=89)
    dashboard = get_inventory_dashboard(
        db,
        branch_scope=branch_scope,
        filters=DashboardFilters(
            branch_id=branch_id_for_default_scope(branch_scope),
            start_date=start_date,
            end_date=end_date,
        ),
    )
    data = safe_data(
        {
            "period_start": dashboard.period_start,
            "period_end": dashboard.period_end,
            "count": dashboard.summary.slow_moving_stock_count,
            "items": dashboard.slow_moving_stock[:10],
        }
    )
    return AIToolResult(
        name="get_slow_moving_products",
        description="Stock-on-hand products with no sales in the selected period.",
        data=data,
    )


def get_pending_purchase_orders(
    db: Session,
    *,
    branch_scope: BranchScope,
) -> AIToolResult:
    start_date, end_date = month_bounds(today())
    dashboard = get_purchase_orders_dashboard(
        db,
        branch_scope=branch_scope,
        filters=DashboardFilters(
            branch_id=branch_id_for_default_scope(branch_scope),
            start_date=start_date,
            end_date=end_date,
        ),
    )
    orders: list[dict[str, Any]] = []
    for status in OPEN_ORDER_STATUSES:
        orders.extend(
            list_data(
                query_purchase_orders(
                    db,
                    branch_scope=branch_scope,
                    filters=PurchaseOrderFilters(
                        branch_id=branch_id_for_default_scope(branch_scope),
                        status=status,
                        limit=MAX_LIST_ITEMS,
                    ),
                )
            )
        )
    data = safe_data(
        {
            "period_start": dashboard.period_start,
            "period_end": dashboard.period_end,
            "summary": dashboard.summary,
            "by_status": dashboard.by_status,
            "orders": orders[:10],
        }
    )
    return AIToolResult(
        name="get_pending_purchase_orders",
        description="Open purchase order queue, status counts, and recent open purchase orders.",
        data=data,
    )


def get_reorder_recommendations(
    db: Session,
    *,
    branch_scope: BranchScope,
) -> AIToolResult:
    recommendations = query_reorder_recommendations(
        db,
        branch_scope=branch_scope,
        filters=ReorderFilters(
            branch_id=branch_id_for_default_scope(branch_scope),
            lookback_days=30,
            as_of_date=today(),
        ),
    )
    actionable = [
        recommendation
        for recommendation in recommendations
        if Decimal(str(recommendation.suggested_reorder_quantity)) > 0
    ]
    data = safe_data(
        {
            "count": len(actionable),
            "items": actionable[:10],
        }
    )
    return AIToolResult(
        name="get_reorder_recommendations",
        description="Reorder recommendations based on stock, target stock, sales velocity, and supplier lead time.",
        data=data,
    )


def get_forecast_summary(
    db: Session,
    *,
    branch_scope: BranchScope,
) -> AIToolResult:
    forecast = run_forecast(
        db,
        payload=ForecastRunCreate(
            forecast_type=ForecastType.DEMAND,
            horizon_days=7,
            branch_id=branch_id_for_default_scope(branch_scope),
            as_of_date=today(),
        ),
        branch_scope=branch_scope,
    )
    data = safe_data(
        {
            "forecast_type": forecast.forecast_type,
            "horizon_days": forecast.horizon_days,
            "branch_id": forecast.branch_id,
            "branch_name": forecast.branch_name,
            "forecast_start_date": forecast.forecast_start_date,
            "forecast_end_date": forecast.forecast_end_date,
            "forecast_value": forecast.forecast_value,
            "average_daily_value": forecast.average_daily_value,
            "trend_label": forecast.trend_label,
            "trend_percent": forecast.trend_percent,
            "insufficient_data": forecast.insufficient_data,
            "message": forecast.message,
        }
    )
    return AIToolResult(
        name="get_forecast_summary",
        description="Seven-day demand forecast from the forecasting service.",
        data=data,
    )


def is_delete_request(message: str) -> bool:
    lowered = message.lower()
    return any(word in lowered for word in ["delete", "remove permanently", "drop table", "erase"])


def is_write_request(message: str) -> bool:
    lowered = message.lower()
    write_phrases = [
        "approve",
        "cancel",
        "receive",
        "adjust stock",
        "update threshold",
        "change threshold",
        "submit purchase order",
        "mark ordered",
        "mark as ordered",
        "create purchase order",
        "create po",
        "generate purchase order",
        "place order",
        "make order",
    ]
    return any(phrase in lowered for phrase in write_phrases)


def route_intent(message: str) -> str:
    lowered = message.lower()
    if is_delete_request(lowered):
        return "forbidden_write_action"
    if is_write_request(lowered):
        return "confirmation_required"
    if "forecast" in lowered or "next week" in lowered or "demand" in lowered:
        return "forecast_summary"
    if "reorder" in lowered or "order today" in lowered or "should i order" in lowered:
        return "reorder_recommendations"
    if "low" in lowered and "stock" in lowered:
        return "low_stock_items"
    if "top" in lowered or "best-selling" in lowered or "best selling" in lowered:
        return "top_products"
    if "branch" in lowered and ("best" in lowered or "performed" in lowered or "performance" in lowered):
        return "branch_performance"
    if "slow" in lowered or "dead stock" in lowered or "not moving" in lowered:
        return "slow_moving_products"
    if "pending" in lowered and ("order" in lowered or "purchase" in lowered or "po" in lowered):
        return "pending_purchase_orders"
    if "sales" in lowered or "revenue" in lowered or "profit" in lowered:
        return "sales_summary"
    return "unknown"


def answer_sales_summary(tool: AIToolResult) -> str:
    summary = tool.data["summary"]
    period_start = tool.data["period_start"]
    period_end = tool.data["period_end"]
    top_products = tool.data.get("top_products", [])
    top_line = ""
    if top_products:
        product = top_products[0]
        top_line = (
            f" Top product: {product['product_name']} with {quantity(product['units_sold'])} units "
            f"and {money(product['revenue'])} revenue."
        )
    if int(summary["transaction_count"]) == 0:
        return f"No sales were recorded from {period_start} to {period_end} for your accessible branch scope."
    return (
        f"Sales from {period_start} to {period_end}: {money(summary['revenue'])} revenue, "
        f"{money(summary['gross_profit'])} gross profit, {quantity(summary['units_sold'])} units, "
        f"{summary['transaction_count']} transactions, and {money(summary['average_order_value'])} average order value."
        f"{top_line}"
    )


def answer_low_stock(tool: AIToolResult) -> str:
    items = tool.data.get("items", [])
    if not items:
        return "No low-stock products were found in your accessible branch scope."
    lines = [
        (
            f"{item['product_name']} at {item['branch_name']} has {quantity(item['quantity_on_hand'])} on hand "
            f"against a threshold of {quantity(item['reorder_threshold'])}."
        )
        for item in items[:MAX_LIST_ITEMS]
    ]
    return f"{tool.data['count']} low-stock inventory rows need attention. " + " ".join(lines)


def answer_top_products(tool: AIToolResult) -> str:
    items = tool.data.get("items", [])
    if not items:
        return f"No product sales were found from {tool.data['period_start']} to {tool.data['period_end']}."
    lines = [
        (
            f"{index}. {item['product_name']} sold {quantity(item['units_sold'])} units "
            f"for {money(item['revenue'])} revenue"
        )
        for index, item in enumerate(items[:MAX_LIST_ITEMS], start=1)
    ]
    return (
        f"Top-selling products from {tool.data['period_start']} to {tool.data['period_end']}: "
        + "; ".join(lines)
        + "."
    )


def answer_branch_performance(tool: AIToolResult) -> str:
    branches = tool.data.get("branch_performance", [])
    if not branches:
        return f"No branch sales were found from {tool.data['period_start']} to {tool.data['period_end']}."
    best = branches[0]
    comparisons = [
        f"{branch['branch_name']}: {money(branch['revenue'])}"
        for branch in branches[:MAX_LIST_ITEMS]
    ]
    return (
        f"{best['branch_name']} performed best from {tool.data['period_start']} to {tool.data['period_end']} "
        f"with {money(best['revenue'])} revenue, {quantity(best['units_sold'])} units, "
        f"and {best['transaction_count']} transactions. Branch comparison: "
        + "; ".join(comparisons)
        + "."
    )


def answer_slow_moving(tool: AIToolResult) -> str:
    items = tool.data.get("items", [])
    if not items:
        return f"No slow-moving stock was found from {tool.data['period_start']} to {tool.data['period_end']}."
    lines = [
        (
            f"{item['product_name']} at {item['branch_name']} has {quantity(item['quantity_on_hand'])} units "
            f"worth {money(item['stock_value'])}; last sale: {item['last_sale_date'] or 'no recorded sale'}"
        )
        for item in items[:MAX_LIST_ITEMS]
    ]
    return f"{tool.data['count']} slow-moving inventory rows were found. " + " ".join(lines)


def answer_pending_purchase_orders(tool: AIToolResult) -> str:
    summary = tool.data["summary"]
    orders = tool.data.get("orders", [])
    if not orders:
        return "No open purchase orders were found in your accessible branch scope."
    lines = [
        (
            f"{order['po_number']} is {order['status']} for {order['supplier_name']} at {order['branch_name']} "
            f"with value {money(order['total_amount'])}"
        )
        for order in orders[:MAX_LIST_ITEMS]
    ]
    return (
        f"There are {summary['pending_purchase_orders']} open purchase orders, including "
        f"{summary['pending_approval_count']} pending approval and {summary['ordered_count']} ordered. "
        + " ".join(lines)
    )


def answer_reorder(tool: AIToolResult) -> str:
    items = tool.data.get("items", [])
    if not items:
        return "No reorder quantities are currently suggested from the available stock and velocity data."
    lines = [
        (
            f"{item['product_name']} at {item['branch_name']} is {item['priority']} priority; "
            f"order {quantity(item['suggested_reorder_quantity'])} units from {item['supplier_name']} "
            f"for estimated cost {money(item['estimated_cost'])}"
        )
        for item in items[:MAX_LIST_ITEMS]
    ]
    return (
        f"{tool.data['count']} items have suggested reorder quantities. "
        + " ".join(lines)
        + " I can suggest a purchase order draft, but creation must be confirmed by an authorized user."
    )


def answer_forecast(tool: AIToolResult) -> str:
    if tool.data["insufficient_data"]:
        return tool.data["message"]
    trend = str(tool.data["trend_label"]).replace("_", " ")
    return (
        f"Next week's demand forecast is {quantity(tool.data['forecast_value'])} units "
        f"from {tool.data['forecast_start_date']} to {tool.data['forecast_end_date']}. "
        f"Average daily demand is {quantity(tool.data['average_daily_value'])} units and the trend is {trend}. "
        f"{tool.data['message']}"
    )


def deterministic_result(
    db: Session,
    *,
    message: str,
    branch_scope: BranchScope,
) -> IntentResult:
    intent = route_intent(message)
    anchor = today()
    month_start, month_end = month_bounds(anchor)

    if intent == "forbidden_write_action":
        return IntentResult(
            intent=intent,
            response=(
                "I cannot delete or erase business records. Use controlled operational screens for safe edits, "
                "and keep audit logs intact."
            ),
            tool_results=[],
            requires_confirmation=True,
            suggested_action="Write action refused",
        )
    if intent == "confirmation_required":
        return IntentResult(
            intent=intent,
            response=(
                "That sounds like a write action. I did not change any stock, sales, or purchase order records. "
                "A confirmed, permission-checked workflow is required before operational changes can run."
            ),
            tool_results=[],
            requires_confirmation=True,
            suggested_action="Confirm action in a dedicated workflow",
        )
    if intent == "forecast_summary":
        tool = get_forecast_summary(db, branch_scope=branch_scope)
        return IntentResult(intent=intent, response=answer_forecast(tool), tool_results=[tool])
    if intent == "reorder_recommendations":
        tool = get_reorder_recommendations(db, branch_scope=branch_scope)
        return IntentResult(intent=intent, response=answer_reorder(tool), tool_results=[tool])
    if intent == "low_stock_items":
        tool = get_low_stock_items(db, branch_scope=branch_scope)
        return IntentResult(intent=intent, response=answer_low_stock(tool), tool_results=[tool])
    if intent == "top_products":
        tool = get_top_products(db, branch_scope=branch_scope)
        return IntentResult(intent=intent, response=answer_top_products(tool), tool_results=[tool])
    if intent == "branch_performance":
        tool = get_sales_summary(db, branch_scope=branch_scope, start_date=month_start, end_date=month_end)
        return IntentResult(intent=intent, response=answer_branch_performance(tool), tool_results=[tool])
    if intent == "slow_moving_products":
        tool = get_slow_moving_products(db, branch_scope=branch_scope)
        return IntentResult(intent=intent, response=answer_slow_moving(tool), tool_results=[tool])
    if intent == "pending_purchase_orders":
        tool = get_pending_purchase_orders(db, branch_scope=branch_scope)
        return IntentResult(intent=intent, response=answer_pending_purchase_orders(tool), tool_results=[tool])
    if intent == "sales_summary":
        if "today" in message.lower():
            start_date = end_date = anchor
        elif "last month" in message.lower():
            start_date, end_date = previous_month_bounds(anchor)
        else:
            start_date, end_date = month_start, month_end
        tool = get_sales_summary(db, branch_scope=branch_scope, start_date=start_date, end_date=end_date)
        return IntentResult(intent=intent, response=answer_sales_summary(tool), tool_results=[tool])

    return IntentResult(
        intent="unknown",
        response=(
            "I can answer sales, low-stock, reorder, top-product, branch performance, slow-moving stock, "
            "pending order, and forecast questions using backend tools. Try: Which items should I reorder today?"
        ),
        tool_results=[],
    )


def output_text_from_openai_response(payload: dict[str, Any]) -> str | None:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()
    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return None


def format_with_openai(*, user_message: str, deterministic_answer: str, tool_results: list[AIToolResult]) -> str | None:
    if not settings.openai_api_key:
        return None

    tool_payload = jsonable_encoder([tool.__dict__ for tool in tool_results])
    prompt = (
        "Rewrite the deterministic business answer in a concise, helpful dashboard-assistant style. "
        "Do not add, remove, round differently, or invent any number. "
        "If the tool data is missing, keep the missing-data explanation. "
        f"User question: {user_message}\n"
        f"Deterministic answer: {deterministic_answer}\n"
        f"Tool data: {tool_payload}"
    )
    try:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You format retail analytics answers. You must only use provided tool data "
                            "and must not invent business numbers."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_output_tokens": 450,
            },
            timeout=12,
        )
        response.raise_for_status()
        return output_text_from_openai_response(response.json())
    except Exception:
        return None


def run_ai_chat(
    db: Session,
    *,
    payload: AIChatRequest,
    user: User,
    branch_scope: BranchScope,
) -> AIChatResponse:
    session = get_or_create_session(db, payload=payload, user=user)
    user_message = AIChatMessage(
        session_id=session.id,
        sender=ChatSender.USER,
        message=payload.message.strip(),
        metadata_json=None,
    )
    db.add(user_message)
    db.flush()

    result = deterministic_result(db, message=payload.message, branch_scope=branch_scope)
    provider_response = format_with_openai(
        user_message=payload.message,
        deterministic_answer=result.response,
        tool_results=result.tool_results,
    )
    assistant_text = provider_response or result.response
    metadata = {
        "intent": result.intent,
        "tool_calls": [tool.__dict__ for tool in result.tool_results],
        "requires_confirmation": result.requires_confirmation,
        "suggested_action": result.suggested_action,
        "provider": "openai" if provider_response else "deterministic",
        "guardrails": [
            "database_backed_tools_for_numbers",
            "no_deletions",
            "confirmation_required_for_writes",
            "role_and_branch_scope_enforced",
        ],
    }
    assistant_message = AIChatMessage(
        session_id=session.id,
        sender=ChatSender.ASSISTANT,
        message=assistant_text,
        metadata_json=safe_data(metadata),
    )
    db.add(assistant_message)
    session.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return AIChatResponse(
        session_id=session.id,
        intent=result.intent,
        response=assistant_text,
        tool_calls=[
            AIToolCallRead(name=tool.name, description=tool.description, data=tool.data)
            for tool in result.tool_results
        ],
        requires_confirmation=result.requires_confirmation,
        suggested_action=result.suggested_action,
        user_message=chat_message_read(user_message),
        assistant_message=chat_message_read(assistant_message),
    )
