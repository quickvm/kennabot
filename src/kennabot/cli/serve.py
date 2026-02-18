"""The ``kennabot serve`` command — starts the bot."""

from __future__ import annotations

import asyncio

import typer


def serve(
    port: int = typer.Option(8080, help="Health endpoint port."),
    log_level: str = typer.Option(
        "",
        help="Override log level (DEBUG, INFO, WARNING, ERROR). Uses KENNABOT_LOG_LEVEL if empty.",
    ),
) -> None:
    """Start KennaBot (Socket Mode + health endpoint)."""
    from kennabot.main import run

    asyncio.run(run(port_override=port, log_level_override=log_level or None))
