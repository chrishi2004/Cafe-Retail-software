from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cafe_orders import StaffOrderItemInput


class CafeCheckoutRequest(BaseModel):
    branch_id: int = Field(ge=1)
    order_type: Literal['counter', 'takeaway'] = 'counter'
    items: list[StaffOrderItemInput] = Field(min_length=1, max_length=25)
    payment_mode_id: int = Field(ge=1)
    reference_number: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(extra='forbid')
