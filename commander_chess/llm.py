"""LLM helpers — square notation in prompts, grid coords for Realm Fabric."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

import chess
from openai import APIError
from pydantic import BaseModel, Field, ValidationError

from commander_chess.env import load_project_env

load_project_env()

from src.llm.client import (  # noqa: E402
    LLMParseError,
    _strip_json_wrapper,
    get_llm_client,
)
from src.llm.schemas import AgentCompoundTurn  # noqa: E402
from src.llm.types import LLMResponse  # noqa: E402

logger = logging.getLogger(__name__)

_SQUARE_RE = re.compile(r"^[a-h][1-8]$", re.IGNORECASE)


class ChessPieceTurn(BaseModel):
    """Minimal chess LLM output — only fields the model needs to produce."""

    reasoning: str = Field(max_length=200)
    move: str = Field(description='Destination square, e.g. "e4".')


def chess_turn_to_compound(turn: ChessPieceTurn) -> AgentCompoundTurn:
    """Fill Realm Fabric compound-turn defaults (look/say/action unused in chess)."""
    return AgentCompoundTurn(
        reasoning=turn.reasoning,
        move=normalize_move_to_grid(turn.move),
        look=None,
        say=None,
        action="none",
        target=None,
        verb=None,
    )


def normalize_move_to_grid(move: str) -> str:
    """
    Convert chess square notation (e.g. h6) to Realm Fabric grid \"x,y\".

    Already-grid values are passed through unchanged.
    """
    text = move.strip()
    if not text:
        return text
    if "," in text:
        return text
    if _SQUARE_RE.match(text):
        square = chess.parse_square(text.lower())
        return f"{chess.square_file(square)},{chess.square_rank(square)}"
    return text


def _parse_json_payload(content: str) -> dict[str, Any]:
    text = _strip_json_wrapper(content)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise LLMParseError("ERR:INVALID_JSON: expected a JSON object")
    return payload


def _chat_completion(
    client,
    *,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
):
    messages = [{"role": "user", "content": prompt}]
    base_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        return client.chat.completions.create(
            **base_kwargs,
            response_format={"type": "json_object"},
        )
    except APIError as exc:
        if exc.status_code == 400:
            logger.warning(
                "Model %s rejected json_object response_format; retrying without it",
                model,
            )
            return client.chat.completions.create(**base_kwargs)
        raise


def get_chess_compound_turn(
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> LLMResponse:
    """Request a chess piece turn; model returns reasoning + destination square only."""
    client = get_llm_client()
    model = model or os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    if max_tokens is None:
        max_tokens = int(os.getenv("CHESS_MAX_OUTPUT_TOKENS", "150"))

    response = _chat_completion(
        client,
        model=model,
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty content")

    try:
        payload = _parse_json_payload(content)
        parsed_chess = ChessPieceTurn.model_validate(payload)
        parsed = chess_turn_to_compound(parsed_chess)
    except (json.JSONDecodeError, ValidationError, LLMParseError) as exc:
        logger.warning("LLM JSON parse failed for model %s: %s", model, exc)
        raise LLMParseError(f"ERR:INVALID_JSON: {exc}") from exc

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None

    return LLMResponse(
        parsed=parsed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        raw_response=content,
    )
