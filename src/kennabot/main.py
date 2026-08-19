"""KennaBot core startup — initializes the app, loads plugins, and runs the bot."""

from __future__ import annotations

import asyncio
import logging
import signal

from kennabot.app import create_bolt_app, create_fastapi_app, start_socket_mode
from kennabot.config import get_settings
from kennabot.database import close_db, init_db
from kennabot.plugins import load_plugins


async def run(
    *,
    port_override: int | None = None,
    log_level_override: str | None = None,
) -> None:
    """Initialize all components and start KennaBot.

    Args:
        port_override: If set, override the health endpoint port (default 8080).
        log_level_override: If set, override the log level from settings.
    """
    settings = get_settings()
    effective_log_level = log_level_override or settings.log_level
    effective_port = port_override or 8080

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, effective_log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("kennabot")
    logger.info("Starting KennaBot v%s", "0.1.0")

    # Initialize database
    await init_db(settings)

    # Create Slack Bolt app
    bolt_app = create_bolt_app(settings)

    # Create FastAPI app (for health checks and future HTTP endpoints)
    api = create_fastapi_app(settings)

    # Load plugins
    await load_plugins(bolt_app, settings)

    # Start Socket Mode
    handler = await start_socket_mode(bolt_app, settings)

    # Start uvicorn in a separate task
    import uvicorn

    uvicorn_config = uvicorn.Config(
        app=api,
        host="0.0.0.0",
        port=effective_port,
        log_level=effective_log_level.lower(),
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    async def run_uvicorn() -> None:
        await uvicorn_server.serve()

    async def run_socket_mode() -> None:
        await handler.start_async()

    logger.info(
        "KennaBot is running! (Socket Mode + health endpoint on :%d)",
        effective_port,
    )

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _handle_signal(sig: int) -> None:
        logger.info("Received signal %s, initiating shutdown...", signal.Signals(sig).name)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # Create tasks
    socket_mode_task = asyncio.create_task(run_socket_mode())
    uvicorn_task = asyncio.create_task(run_uvicorn())

    try:
        # Run until a shutdown signal is received or a task exits unexpectedly.
        done, pending = await asyncio.wait(
            [socket_mode_task, uvicorn_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if exc:
                logger.error("Task exited with error: %s", exc)
    finally:
        logger.info("Shutting down KennaBot...")
        uvicorn_server.should_exit = True
        socket_mode_task.cancel()
        uvicorn_task.cancel()
        await asyncio.gather(socket_mode_task, uvicorn_task, return_exceptions=True)
        await handler.close_async()
        await close_db()
        logger.info("KennaBot stopped")
