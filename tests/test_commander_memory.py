"""Memory module: ally-only orders, turn-scoped display."""

from __future__ import annotations

import chess
from src.memory_modules.base import MemoryRenderContext

from commander_chess.bootstrap import create_session
from commander_chess.memory.commander_orders import (
    CommanderOrdersModule,
    is_commander_orders_module,
)


def _agent_by_name(session, prefix: str):
    for agent in session.areas["board"].agents:
        if agent.name.startswith(prefix):
            return agent
    raise AssertionError(f"Agent starting with {prefix!r} not found")


def _render_for_agent(session, agent) -> str:
    module = agent.memory.module
    area = session.areas["board"]
    return module.render(MemoryRenderContext(agent=agent, area=area))


def test_isinstance_fails_for_dynamically_loaded_module() -> None:
    session, _game = create_session()
    module = _agent_by_name(session, "Black Queen").memory.module
    assert is_commander_orders_module(module)
    assert not isinstance(module, CommanderOrdersModule)


def test_orders_recorded_but_moves_are_not() -> None:
    session, game = create_session()
    game.phase = "needs_order"
    game.pending_color = chess.WHITE
    game.submit_order(session, "Control the center!")
    game.phase = "needs_order"
    game.pending_color = chess.BLACK
    game.submit_order(session, "Keep winning!")

    game.apply_move(session, chess.Move.from_uci("e2e4"))
    game.apply_move(session, chess.Move.from_uci("e7e5"))

    agent = _agent_by_name(session, "Black Queen")
    rendered = _render_for_agent(session, agent)
    assert "No orders from your commander yet" not in rendered
    assert "Turn 1 order: Keep winning!" in rendered
    # Move history is no longer stored in piece memory.
    assert "e4" not in rendered
    assert "e5" not in rendered


def test_black_piece_does_not_see_white_orders() -> None:
    session, game = create_session()
    game.phase = "needs_order"
    game.pending_color = chess.WHITE
    game.submit_order(session, "Win the game!")

    game.apply_move(session, chess.Move.from_uci("g1f3"))
    game.apply_move(session, chess.Move.from_uci("e7e5"))

    black_rendered = _render_for_agent(session, _agent_by_name(session, "Black Queen"))
    white_rendered = _render_for_agent(session, _agent_by_name(session, "White Knight"))

    assert "Win the game!" not in black_rendered
    assert "Win the game!" in white_rendered


def test_standing_order_not_re_recorded_each_ply() -> None:
    session, game = create_session()
    game.phase = "needs_order"
    game.pending_color = chess.WHITE
    game.submit_order(session, "Win the game!")

    game.apply_move(session, chess.Move.from_uci("g1f3"))
    game.apply_move(session, chess.Move.from_uci("e7e5"))
    game.apply_move(session, chess.Move.from_uci("f3e5"))

    agent = _agent_by_name(session, "White Knight")
    module = agent.memory.module
    white_orders = [o for o in module.orders if o.get("side") == "w"]
    assert len(white_orders) == 1
    assert white_orders[0]["text"] == "Win the game!"

    rendered = _render_for_agent(session, agent)
    assert rendered.count("Win the game!") == 1
    assert "Turn 1 order: Win the game!" in rendered
    assert "Turn 3 order:" not in rendered


def test_each_side_sees_only_its_own_orders() -> None:
    session, game = create_session()
    game.phase = "needs_order"
    game.pending_color = chess.WHITE
    game.submit_order(session, "Open with tempo!")
    game.apply_move(session, chess.Move.from_uci("g1f3"))
    game.apply_move(session, chess.Move.from_uci("e7e5"))

    game.phase = "needs_order"
    game.pending_color = chess.BLACK
    game.submit_order(session, "Counter in the center!")
    game.apply_move(session, chess.Move.from_uci("f3e5"))

    white_rendered = _render_for_agent(session, _agent_by_name(session, "White Knight"))
    black_rendered = _render_for_agent(session, _agent_by_name(session, "Black Queen"))

    assert "Open with tempo!" in white_rendered
    assert "Counter in the center!" not in white_rendered

    assert "Counter in the center!" in black_rendered
    assert "Open with tempo!" not in black_rendered

    # No move notation in either side's memory.
    for rendered in (white_rendered, black_rendered):
        assert "Nf3" not in rendered
        assert "1." not in rendered
