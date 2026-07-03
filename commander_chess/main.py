"""CLI entry point."""

from __future__ import annotations

import commander_chess.env  # noqa: F401 — load .env from project root

import uvicorn


def main() -> None:
    uvicorn.run(
        "commander_chess.app:app",
        host="127.0.0.1",
        port=8775,
        reload=False,
    )


if __name__ == "__main__":
    main()
