"""Chess board rendering and coordinate helpers."""

from __future__ import annotations

import chess

PIECE_CHARS = {
    (chess.WHITE, chess.KING): "K",
    (chess.WHITE, chess.QUEEN): "Q",
    (chess.WHITE, chess.ROOK): "R",
    (chess.WHITE, chess.BISHOP): "B",
    (chess.WHITE, chess.KNIGHT): "N",
    (chess.WHITE, chess.PAWN): "P",
    (chess.BLACK, chess.KING): "k",
    (chess.BLACK, chess.QUEEN): "q",
    (chess.BLACK, chess.ROOK): "r",
    (chess.BLACK, chess.BISHOP): "b",
    (chess.BLACK, chess.KNIGHT): "n",
    (chess.BLACK, chess.PAWN): "p",
}

PIECE_PERSONALITIES = {
    chess.PAWN: (
        "You are a pawn in the Commander's army. You advance methodically, "
        "protect fellow soldiers, and seize ground when orders allow."
    ),
    chess.KNIGHT: (
        "You are a knight — unpredictable and bold. You favor forks, "
        "surprise attacks, and flanking maneuvers."
    ),
    chess.BISHOP: (
        "You are a bishop. You control long diagonals and coordinate with "
        "allies along open lines."
    ),
    chess.ROOK: (
        "You are a rook. You dominate open files and ranks, supporting "
        "the line and delivering crushing pressure."
    ),
    chess.QUEEN: (
        "You are the queen — the Commander's most versatile weapon. "
        "Strike where the battle needs you most."
    ),
    chess.KING: (
        "You are the King. When you act, you decide with your own judgment "
        "(your commander moves you directly). Stay alive; the realm depends on you."
    ),
}

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King",
}

# Web UI piece asset keys → static/images/pieces/{white|black}-{type}.png
PIECE_TYPE_KEYS = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def square_to_pos(square: chess.Square) -> tuple[int, int]:
    """Map chess square to Realm Fabric grid (x=file, y=rank)."""
    return chess.square_file(square), chess.square_rank(square)


def pos_to_square(x: int, y: int) -> chess.Square:
    return chess.square(x, y)


def square_name(square: chess.Square) -> str:
    return chess.square_name(square)


def render_board(board: chess.Board, perspective: chess.Color) -> str:
    """
    ASCII battlefield in standard orientation (rank 8 at top, rank 1 at bottom).

    Allied pieces are UPPERCASE; enemy pieces are lowercase.
    Empty squares are dots.
    """
    lines: list[str] = []
    for rank in range(7, -1, -1):
        row: list[str] = ""
        for file in range(8):
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece is None:
                row += "."
            else:
                ch = PIECE_CHARS[(piece.color, piece.piece_type)]
                if piece.color == perspective:
                    row += ch.upper()
                else:
                    row += ch.lower()
        lines.append(row)
    return "\n".join(lines)


BOARD_LEGEND = (
    "Battlefield legend: UPPERCASE = your allied pieces, lowercase = enemy pieces, "
    ". = empty square. * before a piece marks YOU (e.g. *P = this pawn is you). "
    "File letters (a–h) label columns above/below the grid only; piece letters inside "
    "the grid are units. Rank numbers label rows (8 at the top, 1 at the bottom), "
    "matching standard chess notation."
)

_PROMPT_FILE_HEADER = " |a b c d e f g h"
_PROMPT_BORDER = "-+" + "-" * 15  # width of "r n b q k b n r"


def render_board_prompt(
    board: chess.Board,
    perspective: chess.Color,
    *,
    you_square: chess.Square | None = None,
) -> str:
    """
    Bordered ASCII battlefield for LLM prompts.

    Always standard orientation (rank 8 at top). File labels sit outside the grid
    so column letters are not confused with pieces.
    """
    lines: list[str] = [_PROMPT_FILE_HEADER, _PROMPT_BORDER]

    for rank in range(7, -1, -1):
        chess_rank = rank + 1
        cells: list[str] = []
        for file in range(8):
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece is None:
                ch = "."
            else:
                ch = PIECE_CHARS[(piece.color, piece.piece_type)]
                ch = ch.upper() if piece.color == perspective else ch.lower()
            if you_square is not None and square == you_square:
                ch = f"*{ch}"
            cells.append(ch)
        lines.append(f"{chess_rank}|" + " ".join(cells))

    lines.extend([_PROMPT_BORDER, _PROMPT_FILE_HEADER])
    return "\n".join(lines)


def position_hint(
    board: chess.Board,
    square: chess.Square,
    perspective: chess.Color,
) -> str:
    """Human-readable tie between square name and the labeled map."""
    name = square_name(square)
    chess_rank = chess.square_rank(square) + 1
    piece = board.piece_at(square)
    if piece is None:
        role = "empty square"
    else:
        role = PIECE_NAMES[piece.piece_type]

    if perspective == chess.WHITE:
        back_rank = 1
        rows_from_back = chess_rank
    else:
        back_rank = 8
        rows_from_back = 9 - chess_rank

    ordinal = _ordinal(rows_from_back)
    return (
        f"You are at {name} ({role}). On the map above, find row {chess_rank} "
        f"inside the grid (marked * on your piece) — the {ordinal} row from your "
        f"back rank (rank {back_rank})."
    )


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def board_grid_for_ui(
    board: chess.Board,
    *,
    viewer_color: chess.Color,
    phase: str,
    selected_square: int | None,
    agent_by_square: dict[int, str],
    legal_from_squares: set[chess.Square],
    move_target_squares: set[chess.Square],
) -> list[list[dict]]:
    """8×8 grid for the web UI (rank 8 at top, standard chess orientation)."""
    viewer_turn = board.turn == viewer_color
    grid: list[list[dict]] = []

    for rank in range(7, -1, -1):
        row: list[dict] = []
        for file in range(8):
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            agent_id = agent_by_square.get(square)

            char: str | None = None
            piece_color: str | None = None
            piece_type: str | None = None
            if piece is not None:
                ch = PIECE_CHARS[(piece.color, piece.piece_type)]
                char = ch.upper() if piece.color == viewer_color else ch.lower()
                piece_color = "w" if piece.color == chess.WHITE else "b"
                piece_type = PIECE_TYPE_KEYS[piece.piece_type]

            is_king = piece is not None and piece.piece_type == chess.KING
            is_ally = piece is not None and piece.color == viewer_color
            selectable = (
                viewer_turn
                and phase == "select_piece"
                and not board.is_game_over()
                and square in legal_from_squares
                and is_ally
            )
            is_target = (
                viewer_turn
                and phase == "resolve_move"
                and square in move_target_squares
            )

            row.append(
                {
                    "x": file,
                    "y": rank,
                    "label": square_name(square),
                    "piece": char,
                    "piece_color": piece_color,
                    "piece_type": piece_type,
                    "agent_id": agent_id,
                    "selectable": selectable,
                    "is_king": is_king,
                    "manual_move": is_king and is_ally,
                    "is_target": is_target,
                    "selected": square == selected_square,
                    "light": (file + rank) % 2 == 1,
                }
            )
        grid.append(row)
    return grid
