"""Bootstrap a Commander Chess session."""

from __future__ import annotations

import json
from pathlib import Path

import chess
from realm_fabric import PromptBlock, Session, load_profile, register_memory_module_from_path

from commander_chess.chess.board import PIECE_PERSONALITIES, square_name, square_to_pos
from commander_chess.game_state import GameSettings, GameState

MEMORY_MODULE_PATH = Path(__file__).resolve().parent / "memory" / "commander_orders.py"
CHESS_AREA_ID = "board"


def chess_prompt_blocks() -> list[PromptBlock]:
    return [
        PromptBlock(type="slot", name="character"),
        PromptBlock(
            type="text",
            content="\n\nYou receive battlefield intelligence and standing orders below.\n",
        ),
        PromptBlock(type="slot", name="memory"),
        PromptBlock(
            type="section",
            name="compound_rules",
            content=(
                "\nYou are a chess piece under a human commander. You do NOT choose which piece "
                "moves — that was already decided. Pick exactly ONE legal move from the list.\n\n"
                "Respond with JSON only: reasoning (one short sentence, under 120 chars) and "
                "move (destination square, e.g. \"e4\")."
            ),
        ),
        PromptBlock(
            type="section",
            name="output_format",
            content='{"reasoning": "Brief tactical rationale.", "move": "e4"}',
        ),
    ]


def register_commander_memory() -> None:
    register_memory_module_from_path(str(MEMORY_MODULE_PATH))


def create_session(settings: GameSettings | None = None) -> tuple[Session, GameState]:
    register_commander_memory()
    session = Session.from_profile(load_profile("default_compound"))
    session.create_area(CHESS_AREA_ID, description="The battlefield.", width=8, height=8)
    session.set_active_area(CHESS_AREA_ID)
    session.set_prompt_blocks(chess_prompt_blocks())

    game = GameState(settings=settings or GameSettings())
    board = game.board

    for square, piece in board.piece_map().items():
        color = "w" if piece.color == chess.WHITE else "b"
        side = "White" if piece.color == chess.WHITE else "Black"
        type_name = chess.piece_name(piece.piece_type).capitalize()
        name = f"{side} {type_name} ({square_name(square)})"
        personality = PIECE_PERSONALITIES[piece.piece_type]
        result = session.create_agent(
            name=name,
            position=square_to_pos(square),
            area_id=CHESS_AREA_ID,
            personality=personality,
            passive_description=f"{type_name} on {square_name(square)}",
            memory_module="commander_orders",
            move_speed=None,
        )
        agent = result.agent
        if agent is None:
            raise RuntimeError(f"Failed to create agent: {result.message}")
        agent.private_data = json.dumps(
            {
                "color": color,
                "piece_type": piece.piece_type,
                "square": square_name(square),
            }
        )
        game.agent_by_square[square] = agent.id
        game.square_by_agent[agent.id] = square

    game.phase = "lobby"
    game.status_message = "Choose White or Black to begin."
    return session, game
