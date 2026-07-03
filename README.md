# Commander Chess

A **Realm Fabric** demo: two-player chess where human commanders issue written orders, choose *which* piece moves, and each piece (LLM agent) picks *how* — except the **King**, which you move directly.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Quick start

```bash
git clone https://github.com/DaveH-Ghost/Commander__Chess.git
cd Commander__Chess
uv sync
cp .env.example .env    # Windows: copy .env.example .env
```

Add your [OpenRouter](https://openrouter.ai/) API key to `.env`, then:

```bash
uv run commander-chess
```

Open [http://127.0.0.1:8775](http://127.0.0.1:8775). For two players, use **`/white`** and **`/black`** in separate browser tabs or devices.

Without an API key, pieces use a simple heuristic (captures and checks first).

Realm Fabric is installed automatically from [PyPI](https://pypi.org/project/realm-fabric/) — you do not need a separate clone of the engine repo.

### Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | — | LLM moves via OpenRouter |
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash` | Model id |
| `CHESS_MAX_OUTPUT_TOKENS` | `150` | Cap completion size for speed |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` on a server) |
| `PORT` | `8775` | Listen port |

## How to play

1. Open **White** and **Black** player links (`/white`, `/black`) in separate browser tabs or devices.
2. **Issue orders** (140 characters) when prompted.
3. **Select a piece** that has legal moves.
4. **King**: click the piece, then the destination.
5. **Other pieces**: the LLM picks a legal move from the options shown.
6. New orders every **N plies** (White sets the interval before the first order).

Use **Concede** to end a game quickly; **Return to setup** when you are finished reviewing the board.

## Realm Fabric features

- **32 agents** — one per chess piece
- **Custom memory** (`commander_orders`) — ally orders and move history
- **Custom prompts** — battlefield ASCII, slim JSON (`reasoning` + `move`)
- Built on [Realm Fabric](https://github.com/DaveH-Ghost/Realm-Fabric)

## Tests

```bash
uv run pytest
```

## Deploy

See [DEPLOY.md](DEPLOY.md) for running on a VPS (DigitalOcean, etc.) with systemd and HTTPS.

## License

MIT — see [LICENSE](LICENSE).

## Not official chess

This is a technology demo, not a competitive chess product. Rules engine: [python-chess](https://python-chess.readthedocs.io/).
