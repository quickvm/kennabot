"""Async database engine, session management, and Alembic migration runner."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from kennabot.config import Settings

logger = logging.getLogger(__name__)

# Module-level engine and session factory, initialized by init_db()
_engine = None
_session_factory = None


async def init_db(settings: Settings) -> None:
    """Create the async engine, session factory, and run Alembic migrations.

    Alembic's ``upgrade head`` is called programmatically, sharing the engine
    connection so no second connection is opened.  Version directories are
    resolved by ``env.py`` based on ``settings.enabled_plugins``.
    """
    global _engine, _session_factory

    # Ensure the directory for the database file exists
    db_dir = Path(settings.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    _engine = create_async_engine(
        settings.db_url,
        echo=(settings.log_level == "DEBUG"),
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    await _run_migrations(settings)

    logger.info("Database initialized at %s", settings.db_path)


async def _run_migrations(settings: Settings) -> None:
    """Run Alembic ``upgrade head`` programmatically, reusing the open engine."""
    import asyncio
    from pathlib import Path as _Path

    from alembic import command
    from alembic.config import Config

    # Locate alembic.ini: src/kennabot/database.py -> src/kennabot -> src -> project root
    ini_path = _Path(__file__).parent.parent.parent / "alembic.ini"

    alembic_cfg = Config(str(ini_path))
    # Always override the URL from settings — keeps a single source of truth
    alembic_cfg.set_main_option("sqlalchemy.url", settings.db_url)

    # Run in a thread because alembic.command.upgrade is synchronous
    await asyncio.to_thread(command.upgrade, alembic_cfg, "heads")

    logger.debug("Alembic migrations applied")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the async session factory. Raises if init_db() hasn't been called."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory


async def get_session() -> AsyncSession:
    """Create and return a new async session."""
    factory = get_session_factory()
    return factory()


async def close_db() -> None:
    """Dispose of the engine and release connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")
