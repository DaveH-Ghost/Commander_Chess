"""Process-wide session + game state."""

from __future__ import annotations

import chess

from commander_chess.bootstrap import create_session
from commander_chess.game_state import GameSettings, GameState
from commander_chess.player_auth import PlayerSeat, new_player_token
from realm_fabric import Session

_store: SessionStore | None = None


class SessionStore:
    def __init__(self, settings: GameSettings | None = None) -> None:
        self.session, self.game = create_session(settings)
        self.white_seat: PlayerSeat | None = None
        self.black_seat: PlayerSeat | None = None
        self.white_left_review: bool = False
        self.black_left_review: bool = False

    def reset(self, settings: GameSettings | None = None) -> None:
        self.session, self.game = create_session(settings or self.game.settings)
        self.white_seat = None
        self.black_seat = None
        self.white_left_review = False
        self.black_left_review = False

    def match_winding_down(self) -> bool:
        """One commander left review; game board frozen until both return to setup."""
        return self.game.phase == "game_over" and (
            self.white_left_review or self.black_left_review
        )

    def resolve_color(self, token: str | None) -> str | None:
        if not token:
            return None
        if self.white_seat and self.white_seat.token == token:
            return "white"
        if self.black_seat and self.black_seat.token == token:
            return "black"
        return None

    def lobby_info(self) -> dict:
        return {
            "white_taken": self.white_seat is not None,
            "black_taken": self.black_seat is not None,
            "ready": self.white_seat is not None and self.black_seat is not None,
            "match_winding_down": self.match_winding_down(),
        }

    def join(
        self,
        color: str,
        *,
        player_token: str | None = None,
        order_interval: int | None = None,
    ) -> tuple[str | None, str | None]:
        """Claim or reclaim a seat. Returns (error_message, token)."""
        if color not in ("white", "black"):
            return "Invalid color.", None

        if self.match_winding_down():
            return (
                "A finished game is still being reviewed. "
                "Wait until both commanders return to setup.",
                None,
            )

        if player_token:
            resolved = self.resolve_color(player_token)
            if resolved == color:
                return None, player_token
            if resolved is not None:
                return "That token belongs to the other seat.", None

        seat = self.white_seat if color == "white" else self.black_seat
        if seat is not None:
            return f"{color.capitalize()} is already taken.", None

        token = new_player_token()
        new_seat = PlayerSeat(token=token, color=color)
        if color == "white":
            self.white_seat = new_seat
            if order_interval is not None and self.game.can_edit_order_interval():
                self.game.settings.order_interval = order_interval
        else:
            self.black_seat = new_seat

        if self.white_seat and self.black_seat:
            self._begin_match()
        elif self.white_seat:
            self.game.status_message = "Waiting for Black to join…"
        else:
            self.game.status_message = "Waiting for White to join…"
        return None, token

    def concede(self, player_color: str) -> str | None:
        if self.game.phase == "game_over":
            return "Game is already over."
        if self.game.phase == "lobby":
            return "No match in progress."
        opponent = "black" if player_color == "white" else "white"
        self.game.phase = "game_over"
        self.game.winner = opponent
        self.game.end_reason = "concession"
        self.game.selected_agent_id = None
        self.game.selected_square = None
        self.game.status_message = (
            f"{player_color.capitalize()} concedes. {opponent.capitalize()} wins."
        )
        return None

    def dismiss_review(self, player_color: str) -> None:
        """Leave post-game review. Reset lobby only once both commanders have left."""
        if player_color == "white":
            self.white_seat = None
            self.white_left_review = True
        else:
            self.black_seat = None
            self.black_left_review = True

        if self.white_left_review and self.black_left_review:
            self.return_to_lobby()
            return

        opponent = "black" if player_color == "white" else "white"
        self.game.status_message = (
            f"{player_color.capitalize()} returned to setup. "
            f"{opponent.capitalize()} may continue reviewing the board."
        )

    def return_to_lobby(self) -> None:
        settings = self.game.settings
        self.reset(settings)

    def set_order_interval(self, interval: int) -> str | None:
        if not self.game.can_edit_order_interval():
            return "Order refresh interval is locked."
        self.game.settings.order_interval = interval
        return None

    def _begin_match(self) -> None:
        settings = self.game.settings
        white_token = self.white_seat.token if self.white_seat else None
        black_token = self.black_seat.token if self.black_seat else None
        self.session, self.game = create_session(settings)
        if white_token:
            self.white_seat = PlayerSeat(token=white_token, color="white")
        if black_token:
            self.black_seat = PlayerSeat(token=black_token, color="black")
        self.game.phase = "needs_order"
        self.game.pending_color = chess.WHITE
        self.game.status_message = (
            "White commander: issue opening orders (140 characters). "
            "UPPERCASE letters in the battlefield view are your allies; lowercase are enemies."
        )


def get_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_store() -> None:
    global _store
    _store = None


def parse_player_color(color: str) -> chess.Color:
    if color == "white":
        return chess.WHITE
    if color == "black":
        return chess.BLACK
    raise ValueError(f"Invalid player color: {color!r}")
