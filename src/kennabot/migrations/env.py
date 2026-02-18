"""Alembic migration environment for KennaBot.

Supports:
- Async SQLite via aiosqlite
- Per-plugin migration version directories, filtered by ``enabled_plugins``
- Programmatic connection sharing (for use from database.py at startup)
- SQLModel metadata autogenerate

Version directories are discovered by scanning
``src/kennabot/plugins/*/migrations/versions/`` at import time.
If ``KENNABOT_ENABLED_PLUGINS`` is set, only those plugins' version dirs
are included; otherwise all discovered plugin dirs are used.
"""

from __future__ import annotations

import asyncio
import logging
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from alembic.ini if available
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# ---------------------------------------------------------------------------
# Load KennaBot settings (sets DB URL and enabled_plugins)
# ---------------------------------------------------------------------------
from kennabot.config import get_settings as _get_settings  # noqa: E402

_settings = _get_settings()

# Override the DB URL from settings if alembic.ini left it blank
_db_url = config.get_main_option("sqlalchemy.url")
if not _db_url:
    config.set_main_option("sqlalchemy.url", _settings.db_url)

# ---------------------------------------------------------------------------
# Register all models so SQLModel.metadata is fully populated
# ---------------------------------------------------------------------------
import kennabot.models  # noqa: F401, E402 — side-effect import

target_metadata = SQLModel.metadata

# ---------------------------------------------------------------------------
# Discover per-plugin version directories, filtered by enabled_plugins
# ---------------------------------------------------------------------------


def _discover_version_locations() -> list[str]:
    """Return the list of Alembic version directories to use.

    Always includes the core versions dir.  For each plugin whose
    ``migrations/versions/`` directory exists:
    - If ``enabled_plugins`` is non-empty, only include that plugin's dir
      when its name is in the list.
    - If ``enabled_plugins`` is empty, include all discovered plugin dirs.
    """
    env_dir = Path(__file__).parent
    locations: list[str] = [str(env_dir / "versions")]

    enabled: set[str] = set(_settings.enabled_plugins) if _settings.enabled_plugins else set()

    plugins_dir = env_dir.parent / "plugins"
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        plugin_name = plugin_dir.name
        # Skip when an allow-list is set and this plugin isn't in it
        if enabled and plugin_name not in enabled:
            logger.debug(
                "Skipping version dir for plugin '%s' (not in enabled_plugins)",
                plugin_name,
            )
            continue
        versions_dir = plugin_dir / "migrations" / "versions"
        if versions_dir.is_dir():
            locations.append(str(versions_dir))
            logger.debug("Including version location: %s", versions_dir)

    return locations


_version_locations = _discover_version_locations()

# Push the resolved locations back into the Alembic config so that the CLI
# (alembic revision, alembic upgrade, etc.) sees the same set of paths whether
# it is invoked directly or programmatically.
config.set_main_option("version_locations", ":".join(_version_locations))


# ---------------------------------------------------------------------------
# Offline migrations
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL (no engine/DBAPI required).
    Useful for generating SQL scripts without a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_locations=_version_locations,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (async)
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations synchronously using a provided connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_locations=_version_locations,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine from settings and run migrations."""
    # Allow programmatic connection sharing via config.attributes["connection"]
    existing_connection = config.attributes.get("connection", None)
    if existing_connection is not None:
        # Connection was provided by the caller (e.g. database.py at startup)
        do_run_migrations(existing_connection)
        return

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (entry point called by Alembic CLI)."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
