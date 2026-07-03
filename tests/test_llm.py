"""Chess LLM response parsing."""

from __future__ import annotations

from commander_chess.llm import ChessPieceTurn, _parse_json_payload, chess_turn_to_compound


def test_minimal_json_converts_to_compound_turn() -> None:
    turn = ChessPieceTurn.model_validate(
        {"reasoning": "Develop the knight.", "move": "f3"}
    )
    compound = chess_turn_to_compound(turn)
    assert compound.reasoning == "Develop the knight."
    assert compound.move == "5,2"
    assert compound.action == "none"
    assert compound.look is None
    assert compound.say is None


def test_parse_json_payload_extracts_object_from_markdown() -> None:
    payload = _parse_json_payload(
        '```json\n{"reasoning": "Advance.", "move": "e4"}\n```'
    )
    assert payload["move"] == "e4"
