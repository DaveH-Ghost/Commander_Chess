"""Game state and chess ↔ Realm Fabric synchronization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import chess
from realm_fabric import Session

from commander_chess.chess.board import (
    PIECE_NAMES,
    render_board,
    square_name,
    square_to_pos,
)
from commander_chess.chess.moves import legal_move_squares, legal_moves_for_square
from commander_chess.memory.commander_orders import is_commander_orders_module


@dataclass
class GameSettings:
    order_interval: int = 5
    max_order_chars: int = 140


@dataclass
class GameState:
    board: chess.Board = field(default_factory=chess.Board)
    settings: GameSettings = field(default_factory=GameSettings)
    phase: str = "lobby"  # lobby | needs_order | select_piece | resolve_move | game_over
    pending_color: chess.Color | None = None
    selected_agent_id: str | None = None
    selected_square: int | None = None
    last_reasoning: str = ""
    last_reasoning_side: str | None = None
    last_move_san: str = ""
    status_message: str = "Issue your opening orders to begin."
    white_order: str = ""
    black_order: str = ""
    ply_count: int = 0
    agent_by_square: dict[int, str] = field(default_factory=dict)
    square_by_agent: dict[str, int] = field(default_factory=dict)
    winner: str | None = None
    end_reason: str | None = None  # checkmate | stalemate | concession | draw

    def to_dict(self, *, viewer_color: str | None = None) -> dict[str, Any]:
        reasoning = self.last_reasoning
        if viewer_color and self.last_reasoning_side != viewer_color:
            reasoning = ""

        return {
            "fen": self.board.fen(),
            "phase": self.phase,
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "viewer_color": viewer_color,
            "settings": {
                "order_interval": self.settings.order_interval,
                "max_order_chars": self.settings.max_order_chars,
                "order_interval_locked": not self.can_edit_order_interval(),
            },
            "status_message": self.status_message,
            "selected_agent_id": self.selected_agent_id,
            "last_reasoning": reasoning,
            "last_move_san": self.last_move_san,
            "white_order": self.white_order if viewer_color == "white" else "",
            "black_order": self.black_order if viewer_color == "black" else "",
            "ply_count": self.ply_count,
            "winner": self.winner,
            "end_reason": self.end_reason,
            "board_ascii": render_board(
                self.board,
                chess.WHITE if viewer_color == "white" else chess.BLACK,
            )
            if viewer_color
            else render_board(self.board, chess.WHITE),
            "needs_order_from": self._needs_order_color(),
            "check": self.board.is_check() and self.phase != "game_over",
            "game_over": self.phase == "game_over",
        }

    def can_edit_order_interval(self) -> bool:
        """White may set order refresh interval until the first order is submitted."""
        return self.ply_count == 0 and not self.white_order

    def _needs_order_color(self) -> str | None:
        if self.phase != "needs_order":
            return None
        color = self.pending_color
        if color is None:
            color = self.board.turn
        return "white" if color == chess.WHITE else "black"

    def current_standing_order(self, color: chess.Color) -> str:
        return self.white_order if color == chess.WHITE else self.black_order

    def order_due(self) -> bool:
        if self.ply_count == 0:
            return True
        interval = self.settings.order_interval
        return self.ply_count > 0 and self.ply_count % interval == 0

    def begin_turn_cycle(self) -> None:
        if self.board.is_game_over():
            self.phase = "game_over"
            self._set_game_over_message()
            return
        side = self.board.turn
        if self.order_due() or not self.current_standing_order(side):
            self.phase = "needs_order"
            self.pending_color = side
            label = "White" if side == chess.WHITE else "Black"
            self.status_message = f"{label} commander: issue new orders ({self.settings.max_order_chars} chars max)."
            return
        self.phase = "select_piece"
        self.pending_color = side
        label = "White" if side == chess.WHITE else "Black"
        self.status_message = f"{label}: select a piece to act."
        self.selected_agent_id = None
        self.selected_square = None

    def submit_order(self, session: Session, text: str) -> str | None:
        text = text.strip()
        if len(text) > self.settings.max_order_chars:
            return f"Orders must be at most {self.settings.max_order_chars} characters."
        if self.phase != "needs_order":
            return "No order is required right now."
        color = self.pending_color if self.pending_color is not None else self.board.turn
        if color == chess.WHITE:
            self.white_order = text
        else:
            self.black_order = text
        self._record_order_to_memory(session, color, text)
        self.status_message = "Orders received. Select a piece."
        self.phase = "select_piece"
        return None

    def selectable_agents(self, session: Session) -> list[dict[str, Any]]:
        color = self.board.turn
        legal_squares = legal_move_squares(self.board, color)
        items: list[dict[str, Any]] = []
        for square in sorted(legal_squares):
            agent_id = self.agent_by_square.get(square)
            if not agent_id:
                continue
            agent = session.get_agent(agent_id)
            if agent is None:
                continue
            piece = self.board.piece_at(square)
            is_king = piece is not None and piece.piece_type == chess.KING
            items.append(
                {
                    "agent_id": agent_id,
                    "name": agent.name,
                    "square": square_name(square),
                    "is_king": is_king,
                    "manual_move": is_king,
                    "move_count": len(legal_moves_for_square(self.board, square)),
                }
            )
        return items

    def select_piece(self, session: Session, agent_id: str) -> str | None:
        if self.phase not in ("select_piece", "resolve_move"):
            return "Cannot select a piece in the current phase."
        square = self.square_by_agent.get(agent_id)
        if square is None:
            return "Unknown piece."
        piece = self.board.piece_at(square)
        if piece is None or piece.color != self.board.turn:
            return "That piece cannot move now."
        if square not in legal_move_squares(self.board, self.board.turn):
            return "That piece has no legal moves."
        agent = session.get_agent(agent_id)
        if agent is None:
            return "Agent not found."
        session.set_active_agent(agent_id)
        self.selected_agent_id = agent_id
        self.selected_square = square
        self.phase = "resolve_move"
        if piece.piece_type == chess.KING:
            self.status_message = "You take the field. Move your King directly."
        else:
            self.status_message = f"Awaiting {agent.name}'s decision..."
        return None

    def apply_move(
        self,
        session: Session,
        move: chess.Move,
        *,
        reasoning: str = "",
    ) -> None:
        from_square = move.from_square
        to_square = move.to_square
        captured = self.board.piece_at(to_square)
        captured_id = self.agent_by_square.get(to_square) if captured else None
        moving_agent_id = self.agent_by_square.get(from_square)
        san = self.board.san(move)
        is_white = self.board.turn == chess.WHITE

        self.board.push(move)
        self.ply_count += 1
        self.last_move_san = san
        self.last_reasoning = reasoning
        self.last_reasoning_side = "white" if is_white else "black"

        if moving_agent_id:
            agent = session.get_agent(moving_agent_id)
            if agent:
                agent.position = square_to_pos(to_square)
                meta = json.loads(agent.private_data or "{}")
                meta["square"] = square_name(to_square)
                agent.private_data = json.dumps(meta)
                self.square_by_agent[moving_agent_id] = to_square
                self.agent_by_square.pop(from_square, None)
                self.agent_by_square[to_square] = moving_agent_id

        if captured_id and captured_id != moving_agent_id:
            self.square_by_agent.pop(captured_id, None)
            session.delete_agent(captured_id)

        self._append_move_to_memory(session, san, is_white=is_white)
        self.selected_agent_id = None
        self.selected_square = None

        if self.board.is_game_over():
            self.phase = "game_over"
            self._set_game_over_message()
            return
        self.begin_turn_cycle()

    def _record_order_to_memory(
        self, session: Session, color: chess.Color, text: str
    ) -> None:
        side = "w" if color == chess.WHITE else "b"
        turn = self.board.fullmove_number
        for area in session.areas.values():
            for agent in area.agents:
                meta = json.loads(agent.private_data or "{}")
                if meta.get("color") != side:
                    continue
                module = agent.memory.module
                if not is_commander_orders_module(module):
                    continue
                module.add_order(turn, text, side=side)

    def _append_move_to_memory(self, session: Session, san: str, *, is_white: bool) -> None:
        for area in session.areas.values():
            for agent in area.agents:
                module = agent.memory.module
                if not is_commander_orders_module(module):
                    continue
                module.append_ply(self.ply_count, san, is_white=is_white)

    def _set_game_over_message(self) -> None:
        if self.board.is_checkmate():
            winner = not self.board.turn
            self.winner = "white" if winner == chess.WHITE else "black"
            self.end_reason = "checkmate"
            self.status_message = f"Checkmate! {self.winner.capitalize()} wins."
        elif self.board.is_stalemate():
            self.winner = "draw"
            self.end_reason = "stalemate"
            self.status_message = "Stalemate — draw."
        elif self.board.is_insufficient_material():
            self.winner = "draw"
            self.end_reason = "insufficient_material"
            self.status_message = "Draw — insufficient material."
        else:
            self.winner = "draw"
            self.end_reason = "draw"
            self.status_message = "Game over."

    def sync_agents_to_board(self, session: Session) -> None:
        """Rebuild agent position maps from the chess board."""
        self.agent_by_square.clear()
        self.square_by_agent.clear()
        for area in session.areas.values():
            for agent in area.agents:
                meta = json.loads(agent.private_data or "{}")
                sq_name = meta.get("square")
                if not sq_name:
                    continue
                square = chess.parse_square(sq_name)
                piece = self.board.piece_at(square)
                if piece is None:
                    continue
                self.agent_by_square[square] = agent.id
                self.square_by_agent[agent.id] = square
                agent.position = square_to_pos(square)


def piece_label(board: chess.Board, square: chess.Square, color: chess.Color) -> str:
    piece = board.piece_at(square)
    if piece is None:
        return "Unknown"
    side = "White" if color == chess.WHITE else "Black"
    return f"{side} {PIECE_NAMES[piece.piece_type]} ({square_name(square)})"
