"""Legal move helpers."""

from __future__ import annotations

from dataclasses import dataclass

import chess

from commander_chess.chess.board import pos_to_square, square_name, square_to_pos


@dataclass(frozen=True)
class MoveOption:
    uci: str
    san: str
    to_x: int
    to_y: int
    to_label: str
    is_capture: bool
    is_check: bool


def legal_moves_for_square(board: chess.Board, from_square: chess.Square) -> list[MoveOption]:
    options: list[MoveOption] = []
    for move in board.legal_moves:
        if move.from_square != from_square:
            continue
        to_x, to_y = square_to_pos(move.to_square)
        options.append(
            MoveOption(
                uci=move.uci(),
                san=board.san(move),
                to_x=to_x,
                to_y=to_y,
                to_label=square_name(move.to_square),
                is_capture=board.is_capture(move),
                is_check=board.gives_check(move),
            )
        )
    return options


def legal_move_squares(board: chess.Board, color: chess.Color) -> set[chess.Square]:
    squares: set[chess.Square] = set()
    for move in board.legal_moves:
        if board.color_at(move.from_square) == color:
            squares.add(move.from_square)
    return squares


def find_move_by_uci(board: chess.Board, uci: str) -> chess.Move | None:
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return None
    if move in board.legal_moves:
        return move
    return None


def find_move_by_destination(
    board: chess.Board,
    from_square: chess.Square,
    to_x: int,
    to_y: int,
) -> chess.Move | None:
    to_square = pos_to_square(to_x, to_y)
    for move in board.legal_moves:
        if move.from_square == from_square and move.to_square == to_square:
            return move
    return None


def find_move_to_label(
    board: chess.Board,
    from_square: chess.Square,
    to_label: str,
) -> chess.Move | None:
    """Find a legal move to a destination square name (e.g. h6, a1)."""
    try:
        to_square = chess.parse_square(to_label.strip().lower())
    except ValueError:
        return None
    for move in board.legal_moves:
        if move.from_square == from_square and move.to_square == to_square:
            return move
    return None


def pick_heuristic_move(board: chess.Board, from_square: chess.Square) -> chess.Move | None:
    """Simple fallback when no LLM is available."""
    options = legal_moves_for_square(board, from_square)
    if not options:
        return None
    captures = [o for o in options if o.is_capture]
    checks = [o for o in options if o.is_check]
    if checks:
        chosen = checks[0]
    elif captures:
        chosen = captures[0]
    else:
        chosen = options[0]
    return chess.Move.from_uci(chosen.uci)
