from __future__ import annotations

import io
from typing import Annotated
from urllib.parse import quote

import qrcode
from fastapi import APIRouter, Depends
from qrcode.image.svg import SvgPathImage
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.cafe import QRPrintDataRead, QRPrintDataRequest
from app.services.cafe import table_qr_print_data

router = APIRouter(tags=["cafe"])

CafeAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
CurrentScope = Annotated[ScopeContext, Depends(get_scope_context)]
Database = Annotated[Session, Depends(get_db)]


def _svg_data_uri(payload: str) -> str:
    image = qrcode.make(payload, image_factory=SvgPathImage, box_size=8, border=4)
    output = io.BytesIO()
    image.save(output)
    svg = output.getvalue().decode("utf-8")
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


@router.post("/cafe/tables/{table_id}/qr/render", response_model=QRPrintDataRead)
def render_table_qr(
    table_id: int,
    payload: QRPrintDataRequest,
    _admin: CafeAdmin,
    scope: CurrentScope,
    db: Database,
) -> QRPrintDataRead:
    print_data = table_qr_print_data(
        db,
        scope=scope,
        table_id=table_id,
        raw_token=payload.raw_token,
        public_base_url=payload.public_base_url,
    )
    qr_payload = f"{payload.public_base_url.rstrip('/')}/{payload.raw_token}"
    return print_data.model_copy(update={"qr_svg_data_uri": _svg_data_uri(qr_payload)})
