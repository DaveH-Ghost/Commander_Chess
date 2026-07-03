# Deploying Commander Chess

## Requirements

- Ubuntu 22.04+ (or similar)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Domain pointed at your server (optional; HTTPS via Caddy)

Dependencies (including [realm-fabric from PyPI](https://pypi.org/project/realm-fabric/)) are installed by `uv sync` — no second repository to clone.

## Environment variables

Copy `.env.example` to `.env` on the server (never commit `.env`):

```bash
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
CHESS_MAX_OUTPUT_TOKENS=150
```

Optional runtime:

```bash
HOST=127.0.0.1          # use 0.0.0.0 for direct exposure without Caddy
PORT=8775
```

## Quick deploy (DigitalOcean / VPS)

```bash
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/DaveH-Ghost/Commander__Chess.git
cd Commander__Chess
uv sync
cp .env.example .env && nano .env

# Test run (bind all interfaces for IP:PORT access)
HOST=0.0.0.0 PORT=8775 uv run commander-chess
```

Open `http://YOUR_SERVER_IP:8775` (open port 8775 in the firewall only for testing).

## Production (systemd + Caddy)

1. Run the app on localhost only (`HOST=127.0.0.1` in `.env` or the service file).
2. Copy `deploy/commander-chess.service` to `/etc/systemd/system/`, edit `User` and paths.
3. `sudo systemctl daemon-reload && sudo systemctl enable --now commander-chess`
4. Install Caddy, use `deploy/Caddyfile.example` for HTTPS on port 443.

Share these links with players:

- `https://your-domain.com/white`
- `https://your-domain.com/black`

## Notes

- One in-memory game per server process; restart clears the lobby.
- LLM costs are billed by OpenRouter, not your VPS provider.
