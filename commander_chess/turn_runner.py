"""Execute piece moves via LLM or direct commander control."""

from __future__ import annotations

import logging
import os
from typing import Any

import chess
from realm_fabric import AgentCompoundTurn, Session
from src.llm.client import LLMParseError

from commander_chess.chess.moves import (
    find_move_by_destination,
    find_move_by_uci,
    find_move_to_label,
    legal_moves_for_square,
    pick_heuristic_move,
)
from commander_chess.game_state import GameState
from commander_chess.llm import get_chess_compound_turn
from commander_chess.prompt import build_chess_prompt

logger = logging.getLogger(__name__)


def _heuristic_reasoning(exc: BaseException) -> str:
    if not os.getenv("OPENROUTER_API_KEY"):
        return "(Heuristic fallback — OPENROUTER_API_KEY is not set.)"
    if isinstance(exc, LLMParseError):
        return f"(Heuristic fallback — LLM returned invalid JSON: {exc})"
    return f"(Heuristic fallback — {type(exc).__name__}: {str(exc)[:160]})"


def _print_debug_prompt(agent_name: str, prompt: str) -> None:
    """Temporary dev helper — prints the full LLM prompt to the server console."""
    bar = "=" * 72
    print(f"\n{bar}\nPROMPT — {agent_name}\n{bar}\n{prompt}\n{bar}\n", flush=True)


def _parse_compound_move(
    game: GameState,
    compound: AgentCompoundTurn,
) -> tuple[chess.Move | None, str]:
    if game.selected_square is None:
        return None, "No piece selected."
    move_str = (compound.move or "").strip()
    if not move_str:
        return None, "No move provided."

    if "," in move_str:
        parts = move_str.split(",", 1)
        try:
            to_x, to_y = int(parts[0].strip()), int(parts[1].strip())
        except ValueError:
            return None, f"Invalid coordinate move: {move_str!r}"
        move = find_move_by_destination(game.board, game.selected_square, to_x, to_y)
        if move is None:
            return None, f"Illegal move to {move_str}"
        return move, ""

    if len(move_str) in (2, 3) and move_str[0].lower() in "abcdefgh":
        move = find_move_to_label(game.board, game.selected_square, move_str)
        if move is not None:
            return move, ""

    move = find_move_by_uci(game.board, move_str)
    if move is None:
        return None, f"Illegal move: {move_str}"
    return move, ""


def run_manual_move(
    session: Session,
    game: GameState,
    *,
    uci: str | None = None,
    to_x: int | None = None,
    to_y: int | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    if game.phase != "resolve_move":
        return {"ok": False, "message": "Select a piece first."}
    agent_id = agent_id or game.selected_agent_id
    if not agent_id:
        return {"ok": False, "message": "No piece selected."}
    square = game.square_by_agent.get(agent_id)
    if square is None:
        return {"ok": False, "message": "Piece not found."}

    move: chess.Move | None = None
    if uci:
        move = find_move_by_uci(game.board, uci)
    elif to_x is not None and to_y is not None:
        move = find_move_by_destination(game.board, square, to_x, to_y)
    if move is None:
        return {"ok": False, "message": "Illegal move."}

    session.set_active_agent(agent_id)
    compound = AgentCompoundTurn(
        reasoning="The commander moves directly.",
        move=f"{move.to_square % 8},{move.to_square // 8}",
        look=None,
        say=None,
        action="none",
        target=None,
        verb=None,
    )
    gate = session.gate_agent_turn(agent_id)
    if not gate.ok:
        return {"ok": False, "message": gate.message}
    result = session.run_compound_turn(compound, agent_id=agent_id)
    if not result.ok:
        return {"ok": False, "message": result.message}

    game.apply_move(session, move, reasoning="The commander moves directly.")
    return {"ok": True, "message": f"Played {game.last_move_san}", "game": game.to_dict()}


def run_llm_move(session: Session, game: GameState, agent_id: str | None = None) -> dict[str, Any]:
    agent_id = agent_id or game.selected_agent_id
    if not agent_id:
        return {"ok": False, "message": "No piece selected."}
    if game.phase != "resolve_move":
        return {"ok": False, "message": "Select a piece first."}
    square = game.square_by_agent.get(agent_id)
    if square is None:
        return {"ok": False, "message": "Piece not found."}

    options = legal_moves_for_square(game.board, square)
    if not options:
        return {"ok": False, "message": "No legal moves."}

    session.set_active_agent(agent_id)
    gate = session.gate_agent_turn(agent_id)
    if not gate.ok:
        return {"ok": False, "message": gate.message}

    reasoning = ""
    move: chess.Move | None = None
    llm_used = False

    agent = session.get_agent(agent_id)
    agent_name = agent.name if agent else agent_id

    try:
        prompt = build_chess_prompt(session, game, agent_id, options)
        _print_debug_prompt(agent_name, prompt)
        response = get_chess_compound_turn(prompt)
        compound = response.parsed
        reasoning = compound.reasoning or ""
        move, err = _parse_compound_move(game, compound)
        if move is None:
            return {"ok": False, "message": err or "Could not parse LLM move."}
        llm_used = True
        turn_result = session.run_compound_turn(compound, agent_id=agent_id)
        if not turn_result.ok:
            return {"ok": False, "message": turn_result.message}
    except Exception as exc:
        logger.exception("LLM move failed for %s", agent_name)
        prompt = build_chess_prompt(session, game, agent_id, options)
        _print_debug_prompt(f"{agent_name} (heuristic fallback)", prompt)
        move = pick_heuristic_move(game.board, square)
        if move is None:
            return {"ok": False, "message": "No legal moves and LLM unavailable."}
        reasoning = _heuristic_reasoning(exc)
        compound = AgentCompoundTurn(
            reasoning=reasoning,
            move=f"{move.to_square % 8},{move.to_square // 8}",
            look=None,
            say=None,
            action="none",
            target=None,
            verb=None,
        )
        turn_result = session.run_compound_turn(compound, agent_id=agent_id)
        if not turn_result.ok:
            return {"ok": False, "message": turn_result.message}

    game.apply_move(session, move, reasoning=reasoning)
    return {
        "ok": True,
        "message": f"Played {game.last_move_san}",
        "llm_used": llm_used,
        "reasoning": reasoning,
        "game": game.to_dict(),
    }


def run_play_piece(
    session: Session,
    game: GameState,
    agent_id: str,
) -> dict[str, Any]:
    """Select a piece; auto-run LLM for units, pause for manual king."""
    err = game.select_piece(session, agent_id)
    if err:
        return {"ok": False, "message": err}

    square = game.square_by_agent.get(agent_id)
    piece = game.board.piece_at(square) if square is not None else None
    is_manual_king = (
        piece is not None
        and piece.piece_type == chess.KING
    )
    if is_manual_king:
        return {
            "ok": True,
            "message": "Select destination for your King.",
            "awaiting_king_move": True,
            "game": game.to_dict(),
        }
    return run_llm_move(session, game, agent_id=agent_id)
