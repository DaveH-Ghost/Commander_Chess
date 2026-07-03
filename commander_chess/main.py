"""CLI entry point."""

from __future__ import annotations

import os

import commander_chess.env  # noqa: F401 — load .env from project root

import uvicorn


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8775"))
    uvicorn.run(
        "commander_chess.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
