from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.core.config import DeploymentMode, Settings, settings
from app.db.scoping import ScopeViolationError


def include_local_hub_routes(app: FastAPI, app_settings: Settings) -> None:
    from app.api.routes.ai import router as ai_router
    from app.api.routes.auth import router as auth_router
    from app.api.routes.branches import router as branches_router
    from app.api.routes.business_settings import router as business_settings_router
    from app.api.routes.cafe import router as cafe_router
    from app.api.routes.cafe_billing import router as cafe_billing_router
    from app.api.routes.cafe_orders import router as cafe_orders_router
    from app.api.routes.cafe_qr_render import router as cafe_qr_render_router
    from app.api.routes.categories import router as categories_router
    from app.api.routes.continuity import router as continuity_router
    from app.api.routes.customers import router as customers_router
    from app.api.routes.dashboard import router as dashboard_router
    from app.api.routes.exports import router as exports_router
    from app.api.routes.forecasts import router as forecasts_router
    from app.api.routes.inventory import router as inventory_router
    from app.api.routes.invoices import router as invoices_router
    from app.api.routes.products import router as products_router
    from app.api.routes.public_cafe import router as public_cafe_router
    from app.api.routes.purchase_orders import router as purchase_orders_router
    from app.api.routes.sales import router as sales_router
    from app.api.routes.suppliers import router as suppliers_router
    from app.api.routes.sync_status import router as sync_status_router
    from app.api.routes.tax_operation import router as tax_operation_router
    from app.api.routes.ventures import router as ventures_router

    for router in (
        public_cafe_router,
        auth_router,
        ventures_router,
        cafe_orders_router,
        cafe_billing_router,
        cafe_router,
        cafe_qr_render_router,
        sync_status_router,
        continuity_router,
        tax_operation_router,
        business_settings_router,
        categories_router,
        suppliers_router,
        branches_router,
        products_router,
        customers_router,
        invoices_router,
        inventory_router,
        sales_router,
        dashboard_router,
        purchase_orders_router,
        forecasts_router,
        exports_router,
        ai_router,
    ):
        app.include_router(router, prefix=app_settings.api_prefix)


def include_cloud_gateway_routes(app: FastAPI, app_settings: Settings) -> None:
    from app.api.routes.cloud_gateway import router as cloud_gateway_router
    from app.api.routes.hc3_cloud import router as hc3_cloud_router
    from app.api.routes.hc4_cloud import router as hc4_cloud_router

    app.include_router(cloud_gateway_router, prefix=app_settings.api_prefix)
    app.include_router(hc3_cloud_router, prefix=app_settings.api_prefix)
    app.include_router(hc4_cloud_router, prefix=app_settings.api_prefix)


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved_settings = app_settings or settings
    docs_enabled = resolved_settings.resolved_api_docs_enabled
    app = FastAPI(
        title=resolved_settings.app_name,
        description=(
            "Local operational retail and Cafe API."
            if resolved_settings.deployment_mode == DeploymentMode.LOCAL_HUB
            else "Limited hybrid cloud coordination gateway."
        ),
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=resolved_settings.api_prefix)
    if resolved_settings.deployment_mode == DeploymentMode.LOCAL_HUB:
        include_local_hub_routes(app, resolved_settings)
    else:
        include_cloud_gateway_routes(app, resolved_settings)

    @app.exception_handler(ScopeViolationError)
    async def scope_violation_handler(_request, _exc: ScopeViolationError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "not_found",
                    "message": "Resource not found or unavailable.",
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            content = {"error": detail}
        else:
            content = {"error": {"code": "http_error", "message": str(detail)}}
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    return app


app = create_app()
