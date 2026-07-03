# Commander Chess

A **Realm Fabric** demo: chess where you command units with written orders and pick *which* piece moves — but each piece (LLM agent) chooses *how*, unless you select your **King**, in which case you move directly.

## Quick start

```powershell
cd path\to\Commander__Chess
uv sync
copy .env.example .env   # optional — LLM moves need OPENROUTER_API_KEY
uv run commander-chess
```

Open [http://127.0.0.1:8775](http://127.0.0.1:8775)

Without an API key, piece moves fall back to a simple heuristic (captures/checks first). Set `OPENROUTER_API_KEY` in `.env` for LLM-driven pieces.

## How to play

1. **Issue orders** (140 chars) — your standing intent for all pieces.
2. **Select a piece** that has legal moves.
3. **King (White)**: pick the destination yourself — you *are* the commander on the field.
4. **Other pieces**: pick a move manually or click **Let piece decide (LLM)**.
5. New orders every **5 plies** by default (configurable in UI).

Black plays via AI (auto-orders + LLM/heuristic) when enabled.

## Realm Fabric features used

- **32 agents**, no objects — one agent per chess piece
- **Custom memory module** (`commander_orders`) — orders + move log per piece
- **Custom prompt layout** — battlefield ASCII replaces passive vision
- **Compound turns** — `move` field only; LLM or manual king moves
- **FastAPI** web shell (minimal-server pattern)

## Tests

```powershell
uv run pytest
```

## Not official chess

This is a technology demo, not a competitive chess product. Rules engine: [python-chess](https://python-chess.readthedocs.io/).
