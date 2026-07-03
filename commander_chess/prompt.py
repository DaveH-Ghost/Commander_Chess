"""Build LLM prompts for piece agents."""

from __future__ import annotations

import chess

from commander_chess.chess.board import BOARD_LEGEND, position_hint, render_board_prompt
from commander_chess.chess.moves import MoveOption
from commander_chess.game_state import GameState
from realm_fabric import Session


def build_chess_prompt(
    session: Session,
    game: GameState,
    agent_id: str,
    move_options: list[MoveOption],
) -> str:
    agent = session.get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Agent {agent_id} not found")
    square = game.square_by_agent.get(agent_id)
    if square is None:
        raise ValueError("Piece not on board")

    color = chess.WHITE if json_color(agent) == "w" else chess.BLACK
    base = session.build_prompt(agent_id)

    board_view = render_board_prompt(game.board, color, you_square=square)
    hint = position_hint(game.board, square, color)
    order = game.current_standing_order(color)
    interval = game.settings.order_interval
    moves_text = "\n".join(
        f"- {opt.san} → move \"{opt.to_label.lower()}\""
        for opt in move_options
    )

    return (
        f"{base}\n\n"
        f"=== BATTLEFIELD (your view) ===\n"
        f"{BOARD_LEGEND}\n\n"
        f"{board_view}\n\n"
        f"{hint}\n"
        f"Your human commander can only issue new verbal orders once every "
        f"{interval} {'ply' if interval == 1 else 'plies'}.\n"
        f"Standing orders: {order or '(none)'}\n\n"
        f"LEGAL MOVES — pick exactly ONE destination via the move field:\n"
        f"{moves_text}\n"
    )


def json_color(agent) -> str:
    import json

    meta = json.loads(agent.private_data or "{}")
    return meta.get("color", "w")
