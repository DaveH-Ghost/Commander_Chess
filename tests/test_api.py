"""Basic tests without LLM."""

from __future__ import annotations

import chess
from fastapi.testclient import TestClient

from commander_chess.app import create_app, reset_store
from commander_chess.chess.board import render_board, render_board_prompt, position_hint
from commander_chess.chess.moves import find_move_to_label

TOKEN_HEADER = "X-Player-Token"


def _join(client: TestClient, color: str, *, order_interval: int | None = None) -> str:
    body: dict = {"color": color}
    if order_interval is not None:
        body["order_interval"] = order_interval
    res = client.post("/api/join", json=body)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["player_token"]
    assert data["your_color"] == color
    return data["player_token"]


def _auth(token: str) -> dict[str, str]:
    return {TOKEN_HEADER: token}


def _join_both(client: TestClient) -> tuple[str, str]:
    white_token = _join(client, "white", order_interval=5)
    black_token = _join(client, "black")
    return white_token, black_token


def test_render_board_perspective() -> None:
    board = chess.Board()
    text = render_board(board, chess.WHITE)
    lines = text.split("\n")
    assert lines[0] == "rnbqkbnr"
    assert lines[-1] == "RNBQKBNR"


def test_render_board_prompt_black_pawn_a7() -> None:
    board = chess.Board()
    a7 = chess.parse_square("a7")
    text = render_board_prompt(board, chess.BLACK, you_square=a7)
    assert " |a b c d e f g h" in text
    assert "-+" + "-" * 15 in text
    assert "8|R N B Q K B N R" in text
    assert "7|*P P P P P P P P" in text
    assert "1|r n b q k b n r" in text
    hint = position_hint(board, a7, chess.BLACK)
    assert "a7" in hint
    assert "row 7" in hint
    assert "2nd row from your back rank" in hint
    assert "rank 8" in hint


def test_api_lobby_and_order() -> None:
    reset_store()
    client = TestClient(create_app())

    state = client.get("/api/state").json()
    assert state["phase"] == "lobby"

    white_token = _join(client, "white", order_interval=5)
    state = client.get("/api/state", headers=_auth(white_token)).json()
    assert state["phase"] == "lobby"
    assert state["your_color"] == "white"

    black_token = _join(client, "black")
    state = client.get("/api/state", headers=_auth(black_token)).json()
    assert state["phase"] == "needs_order"

    res = client.post(
        "/api/order",
        json={"text": "Control the center!"},
        headers=_auth(white_token),
    )
    assert res.status_code == 200
    state = res.json()
    assert state["phase"] == "select_piece"
    assert len(state["selectable_pieces"]) > 0


def test_join_reclaims_seat_with_token() -> None:
    reset_store()
    client = TestClient(create_app())
    token = _join(client, "white", order_interval=5)
    res = client.post(
        "/api/join",
        json={"color": "white", "player_token": token},
    )
    assert res.status_code == 200
    assert res.json()["player_token"] == token


def test_reasoning_hidden_from_opponent() -> None:
    reset_store()
    client = TestClient(create_app())
    white_token, black_token = _join_both(client)
    client.post(
        "/api/order",
        json={"text": "Advance the e-pawn."},
        headers=_auth(white_token),
    )

    state = client.get("/api/state", headers=_auth(white_token)).json()
    pawn = next(p for p in state["selectable_pieces"] if "Pawn (e2)" in p["name"])
    client.post(
        "/api/play-piece",
        json={"agent_id": pawn["agent_id"]},
        headers=_auth(white_token),
    )

    white_view = client.get("/api/state", headers=_auth(white_token)).json()
    black_view = client.get("/api/state", headers=_auth(black_token)).json()
    assert white_view["last_reasoning"]
    assert black_view["last_reasoning"] == ""


def test_play_piece_auto_move() -> None:
    reset_store()
    client = TestClient(create_app())
    white_token, _ = _join_both(client)
    client.post(
        "/api/order",
        json={"text": "Advance the e-pawn."},
        headers=_auth(white_token),
    )

    state = client.get("/api/state", headers=_auth(white_token)).json()
    pawn = next(p for p in state["selectable_pieces"] if "Pawn (e2)" in p["name"])
    res = client.post(
        "/api/play-piece",
        json={"agent_id": pawn["agent_id"]},
        headers=_auth(white_token),
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["state"]["last_move_san"]


def test_find_move_to_label() -> None:
    board = chess.Board()
    e2 = chess.parse_square("e2")
    move = find_move_to_label(board, e2, "e4")
    assert move is not None
    assert board.san(move) == "e4"


def test_find_move_to_label_rejects_illegal() -> None:
    board = chess.Board()
    e2 = chess.parse_square("e2")
    assert find_move_to_label(board, e2, "e5") is None


def test_concede_sets_winner() -> None:
    reset_store()
    client = TestClient(create_app())
    white_token, black_token = _join_both(client)
    res = client.post("/api/concede", headers=_auth(white_token))
    assert res.status_code == 200
    state = res.json()
    assert state["phase"] == "game_over"
    assert state["winner"] == "black"
    assert state["end_reason"] == "concession"

    black_view = client.get("/api/state", headers=_auth(black_token)).json()
    assert black_view["winner"] == "black"
    assert black_view["game_over"] is True


def test_dismiss_returns_to_lobby() -> None:
    reset_store()
    client = TestClient(create_app())
    white_token, black_token = _join_both(client)
    client.post("/api/concede", headers=_auth(white_token))

    res = client.post("/api/dismiss", headers=_auth(black_token))
    assert res.status_code == 200
    state = res.json()
    assert state["phase"] == "game_over"
    assert state["match_winding_down"] is True

    white_view = client.get("/api/state", headers=_auth(white_token)).json()
    assert white_view["phase"] == "game_over"

    res = client.post("/api/join", json={"color": "white"})
    assert res.status_code == 409

    client.post("/api/dismiss", headers=_auth(white_token))
    assert client.get("/api/state").json()["phase"] == "lobby"


def test_join_blocked_until_both_leave_review() -> None:
    reset_store()
    client = TestClient(create_app())
    white_token, black_token = _join_both(client)
    client.post("/api/concede", headers=_auth(white_token))
    client.post("/api/dismiss", headers=_auth(white_token))

    assert (
        client.get("/api/state", headers=_auth(black_token)).json()["phase"] == "game_over"
    )

    for color in ("white", "black"):
        res = client.post("/api/join", json={"color": color})
        assert res.status_code == 409

    client.post("/api/dismiss", headers=_auth(black_token))
    assert client.post("/api/join", json={"color": "white", "order_interval": 5}).status_code == 200
