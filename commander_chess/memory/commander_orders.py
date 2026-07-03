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


MODULE_DESCRIPTION = (
    "Standing orders from the commander plus a chronological log of game moves."
)


@dataclass
class CommanderOrdersModule:
    """Memory of commander orders and the move history of the whole game."""

    module_id: str = MODULE_ID
    orders: list[dict[str, Any]] = field(default_factory=list)
    move_pairs: list[str] = field(default_factory=list)
    _pending_white: str | None = field(default=None, repr=False)
    _total_turns: int = field(default=0, repr=False)

    def add_order(self, turn: int, text: str, *, side: str) -> None:
        self.orders.append({"turn": turn, "text": text.strip(), "side": side})

    def append_ply(self, ply: int, san: str, *, is_white: bool) -> None:
        if is_white:
            self._pending_white = f"{ply // 2 + 1}. {san}"
        elif self._pending_white:
            self.move_pairs.append(f"{self._pending_white} {san}")
            self._pending_white = None
        else:
            self.move_pairs.append(f"{ply}. ... {san}")

    def render(self, ctx: MemoryRenderContext) -> str:
        import json

        meta = json.loads(ctx.agent.private_data or "{}")
        ally_side = meta.get("color", "w")
        ally_orders = sorted(
            (o for o in self.orders if o.get("side", "w") == ally_side),
            key=lambda o: int(o["turn"]),
        )
        orders_by_turn = {int(o["turn"]): o for o in ally_orders}
        moves_by_turn: dict[int, str] = {}
        for move_line in self.move_pairs:
            moves_by_turn[_parse_move_number(move_line)] = move_line

        pending_turn: int | None = None
        if self._pending_white:
            pending_turn = _parse_move_number(self._pending_white)

        turn_numbers = sorted(
            set(orders_by_turn) | set(moves_by_turn) | ({pending_turn} if pending_turn else set())
        )

        lines: list[str] = []
        for turn in turn_numbers:
            if turn in orders_by_turn:
                order = orders_by_turn[turn]
                lines.append(f"Turn {turn} order: {order['text']}")
            if turn in moves_by_turn:
                lines.append(moves_by_turn[turn])
            elif pending_turn == turn:
                lines.append(self._pending_white)  # type: ignore[arg-type]

        return "\n".join(lines) if lines else "No orders or moves recorded yet."

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
            "move_pairs": list(self.move_pairs),
            "pending_white": self._pending_white,
            "total_turns": self._total_turns,
        }

    def restore_state(self, data: dict[str, Any]) -> None:
        self.orders = list(data.get("orders", []))
        self.move_pairs = list(data.get("move_pairs", []))
        self._pending_white = data.get("pending_white")
        self._total_turns = int(data.get("total_turns", 0))


def create_module(**config: Any) -> CommanderOrdersModule:
    del config
    return CommanderOrdersModule()


def _parse_move_number(move_line: str) -> int:
    first_num = move_line.split(".", 1)[0]
    return int(first_num)
