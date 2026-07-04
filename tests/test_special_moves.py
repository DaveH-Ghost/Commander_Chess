"""Special moves keep agent↔square maps in sync (castling, en passant)."""

from __future__ import annotations

import chess

from commander_chess.bootstrap import create_session


def _sq(name: str) -> chess.Square:
    return chess.parse_square(name)


def _play(game, session, *ucis: str) -> None:
    for uci in ucis:
        game.apply_move(session, chess.Move.from_uci(uci))


def test_castling_relocates_rook_agent() -> None:
    session, game = create_session()
    rook_id = game.agent_by_square[_sq("h1")]

    # Clear the kingside, then castle short.
    _play(
        game,
        session,
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
        "f1c4",
        "g8f6",
        "e1g1",
    )

    # Rook moved h1 -> f1 on the board; its agent mapping must follow.
    assert game.agent_by_square.get(_sq("f1")) == rook_id
    assert _sq("h1") not in game.agent_by_square
    assert game.square_by_agent[rook_id] == _sq("f1")

    rook_agent = session.get_agent(rook_id)
    assert rook_agent is not None

    # And it is selectable again once it is White's turn and the rook can move
    # (the castled rook on f1 can slide to the vacated e1).
    _play(game, session, "a7a5")  # black filler so it is White's turn again
    selectable_ids = {item["agent_id"] for item in game.selectable_agents(session)}
    assert rook_id in selectable_ids


def test_en_passant_removes_captured_pawn_agent() -> None:
    session, game = create_session()

    _play(game, session, "e2e4", "a7a6", "e4e5", "d7d5")
    black_pawn_id = game.agent_by_square[_sq("d5")]
    white_pawn_id = game.agent_by_square[_sq("e5")]

    _play(game, session, "e5d6")  # en passant capture of the d5 pawn

    # Captured pawn's agent is gone and its square mapping cleared.
    assert session.get_agent(black_pawn_id) is None
    assert black_pawn_id not in game.square_by_agent
    assert _sq("d5") not in game.agent_by_square

    # Moving pawn now sits on d6.
    assert game.agent_by_square.get(_sq("d6")) == white_pawn_id
    assert game.square_by_agent[white_pawn_id] == _sq("d6")
