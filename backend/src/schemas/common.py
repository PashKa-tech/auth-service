from pydantic import BaseModel, Field
from typing import Any
from src.core.context import get_request_id

class UnifiedResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str | None = None
    error: Any | None = None
    meta: dict = Field(default_factory=lambda: {"version": "v1", "request_id": get_request_id()})
