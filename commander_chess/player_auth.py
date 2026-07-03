"""Per-browser player seat tokens (server is source of truth for color)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerSeat:
    token: str
    color: str  # "white" | "black"


def new_player_token() -> str:
    return secrets.token_urlsafe(24)
