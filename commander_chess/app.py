"""FastAPI application."""

from __future__ import annotations

import commander_chess.env  # noqa: F401 — load .env from project root before other imports

from pathlib import Path

import chess
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from commander_chess.chess.board import board_grid_for_ui
from commander_chess.chess.moves import legal_move_squares, legal_moves_for_square
from commander_chess.schemas import (
    JoinRequest,
    ManualMoveRequest,
    OrderIntervalRequest,
    OrderRequest,
    PlayerColor,
    SelectPieceRequest,
)
from commander_chess.session_store import get_store, parse_player_color, reset_store
from commander_chess.turn_runner import run_manual_move, run_play_piece

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
PLAYER_TOKEN_HEADER = "X-Player-Token"


def create_app() -> FastAPI:
    app = FastAPI(title="Commander Chess", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/state")
    def get_state(
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = store.resolve_color(x_player_token)
        return _build_state(store, player_color)

    @app.post("/api/join")
    def join(body: JoinRequest) -> dict:
        store = get_store()
        err, token = store.join(
            body.color,
            player_token=body.player_token,
            order_interval=body.order_interval,
        )
        if err:
            raise HTTPException(status_code=409, detail=err)
        payload = _build_state(store, body.color)
        payload["player_token"] = token
        payload["your_color"] = body.color
        return payload

    @app.post("/api/concede")
    def concede(
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = _require_player(store, x_player_token)
        err = store.concede(player_color)
        if err:
            raise HTTPException(status_code=400, detail=err)
        return _build_state(store, player_color)

    @app.post("/api/dismiss")
    def dismiss_match(
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = _require_player(store, x_player_token)
        if store.game.phase != "game_over":
            raise HTTPException(status_code=400, detail="The match is still in progress.")
        store.dismiss_review(player_color)
        if store.game.phase == "lobby":
            return _build_state(store, None)
        return _build_state(store, player_color)

    @app.post("/api/settings/order-interval")
    def set_order_interval(
        body: OrderIntervalRequest,
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = _require_player(store, x_player_token)
        if player_color != "white":
            raise HTTPException(status_code=403, detail="Only White may set order refresh.")
        err = store.set_order_interval(body.order_interval)
        if err:
            raise HTTPException(status_code=400, detail=err)
        return _build_state(store, player_color)

    @app.post("/api/order")
    def submit_order(
        body: OrderRequest,
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = _require_player(store, x_player_token)
        _require_order_turn(store, player_color)
        err = store.game.submit_order(store.session, body.text)
        if err:
            raise HTTPException(status_code=400, detail=err)
        return _build_state(store, player_color)

    @app.post("/api/play-piece")
    def play_piece(
        body: SelectPieceRequest,
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = _require_player(store, x_player_token)
        _require_piece_turn(store, player_color)
        result = run_play_piece(store.session, store.game, body.agent_id)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["message"])
        payload = {**result, "state": _build_state(store, player_color)}
        return payload

    @app.post("/api/move/manual")
    def manual_move(
        body: ManualMoveRequest,
        x_player_token: str | None = Header(default=None, alias=PLAYER_TOKEN_HEADER),
    ) -> dict:
        store = get_store()
        player_color = _require_player(store, x_player_token)
        _require_piece_turn(store, player_color)
        result = run_manual_move(
            store.session,
            store.game,
            uci=body.uci,
            to_x=body.to_x,
            to_y=body.to_y,
            agent_id=body.agent_id,
        )
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return {**result, "state": _build_state(store, player_color)}

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        index_path = STATIC_DIR / "index.html"

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(index_path)

        @app.get("/white")
        def white_player() -> FileResponse:
            return FileResponse(index_path)

        @app.get("/black")
        def black_player() -> FileResponse:
            return FileResponse(index_path)

    return app


def _require_player(store, token: str | None) -> PlayerColor:
    if not token:
        raise HTTPException(status_code=401, detail="Missing player token. Rejoin from your player link.")
    color = store.resolve_color(token)
    if not color:
        raise HTTPException(status_code=403, detail="Invalid or expired player token. Rejoin from your player link.")
    if store.game.phase == "lobby":
        raise HTTPException(status_code=400, detail="Game has not started yet.")
    return color  # type: ignore[return-value]


def _require_order_turn(store, player_color: str) -> None:
    game = store.game
    if game.phase != "needs_order":
        raise HTTPException(status_code=400, detail="No order is required right now.")
    side = (
        game.pending_color
        if game.pending_color is not None
        else game.board.turn
    )
    if parse_player_color(player_color) != side:
        raise HTTPException(status_code=403, detail="Not your turn to issue orders.")


def _require_piece_turn(store, player_color: str) -> None:
    game = store.game
    if game.board.turn != parse_player_color(player_color):
        raise HTTPException(status_code=403, detail="Not your turn.")


def _build_state(store, viewer: str | None) -> dict:
    game = store.game
    viewer_color = parse_player_color(viewer) if viewer else chess.WHITE

    legal_from: set[chess.Square] = set()
    if (
        viewer
        and game.phase == "select_piece"
        and game.board.turn == viewer_color
    ):
        legal_from = legal_move_squares(game.board, game.board.turn)

    move_targets: set[chess.Square] = set()
    if (
        viewer
        and game.phase == "resolve_move"
        and game.selected_square is not None
        and game.board.turn == viewer_color
    ):
        for m in legal_moves_for_square(game.board, game.selected_square):
            move_targets.add(chess.square(m.to_x, m.to_y))

    payload = game.to_dict(viewer_color=viewer)
    payload["your_color"] = viewer
    payload["match_winding_down"] = store.match_winding_down()
    payload["lobby"] = store.lobby_info()
    payload["selectable_pieces"] = (
        game.selectable_agents(store.session)
        if viewer and game.board.turn == viewer_color
        else []
    )
    payload["legal_moves"] = (
        _legal_moves_for_selection(store)
        if viewer
        and game.board.turn == viewer_color
        and game.phase == "resolve_move"
        else []
    )
    payload["board_grid"] = board_grid_for_ui(
        game.board,
        viewer_color=viewer_color if viewer else chess.WHITE,
        phase=game.phase,
        selected_square=game.selected_square,
        agent_by_square=game.agent_by_square,
        legal_from_squares=legal_from,
        move_target_squares=move_targets,
    )
    return payload


def _legal_moves_for_selection(store) -> list[dict]:
    game = store.game
    if game.selected_square is None:
        return []
    return [
        {
            "uci": m.uci,
            "san": m.san,
            "to_x": m.to_x,
            "to_y": m.to_y,
            "to_label": m.to_label,
        }
        for m in legal_moves_for_square(game.board, game.selected_square)
    ]


app = create_app()

__all__ = ["app", "create_app", "reset_store"]
