from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from src.turn_record import TurnRecord

MODULE_ID = "commander_orders"
MODULE_LABEL = "Commander orders"


def is_commander_orders_module(module: object) -> bool:
    """True when module is our custom memory (by id, not class — avoids dynamic-load mismatch)."""
    return getattr(module, "module_id", None) == MODULE_ID


MODULE_DESCRIPTION = "Standing orders issued by the commander to this side."


@dataclass
class CommanderOrdersModule:
    """Memory of the commander's orders for this piece's side (no move log)."""

    module_id: str = MODULE_ID
    orders: list[dict[str, Any]] = field(default_factory=list)
    _total_turns: int = field(default=0, repr=False)

    def add_order(self, turn: int, text: str, *, side: str) -> None:
        self.orders.append({"turn": turn, "text": text.strip(), "side": side})

    def render(self, ctx: MemoryRenderContext) -> str:
        import json

        meta = json.loads(ctx.agent.private_data or "{}")
        ally_side = meta.get("color", "w")
        ally_orders = sorted(
            (o for o in self.orders if o.get("side", "w") == ally_side),
            key=lambda o: int(o["turn"]),
        )
        if not ally_orders:
            return "No orders from your commander yet."
        return "\n".join(
            f"Turn {int(o['turn'])} order: {o['text']}" for o in ally_orders
        )

    def record_turn(self, record: TurnRecord, ctx: MemoryRecordContext) -> None:
        del record, ctx
        self._total_turns += 1

    def record_observation(self, event: WitnessedEvent, ctx: MemoryObserveContext) -> None:
        del event, ctx

    @property
    def total_turns(self) -> int:
        return self._total_turns

    @property
    def stored_turns(self) -> list[TurnRecord]:
        return []

    def export_state(self) -> dict[str, Any]:
        return {
            "orders": list(self.orders),
            "total_turns": self._total_turns,
        }

    def restore_state(self, data: dict[str, Any]) -> None:
        self.orders = list(data.get("orders", []))
        self._total_turns = int(data.get("total_turns", 0))


def create_module(**config: Any) -> CommanderOrdersModule:
    del config
    return CommanderOrdersModule()
