"""API request/response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlayerColor = Literal["white", "black"]


class OrderRequest(BaseModel):
    text: str = Field(max_length=140)


class SelectPieceRequest(BaseModel):
    agent_id: str


class ManualMoveRequest(BaseModel):
    uci: str | None = None
    to_x: int | None = None
    to_y: int | None = None
    agent_id: str | None = None


class JoinRequest(BaseModel):
    color: PlayerColor
    player_token: str | None = None
    order_interval: int | None = Field(default=None, ge=1, le=50)


class OrderIntervalRequest(BaseModel):
    order_interval: int = Field(ge=1, le=50)
