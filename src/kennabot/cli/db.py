"""The ``kennabot db`` command group — database management."""

from __future__ import annotations

from typing import Annotated

import typer

from kennabot.cli.async_typer import AsyncTyper

app = AsyncTyper(name="db", help="Database management commands.")


@app.command()
async def init() -> None:
    """Create the database and run all pending migrations.

    Runs Alembic ``upgrade heads`` — safe to call on an existing database
    (it is a no-op when already at the latest revision).
    """
    from kennabot.config import get_settings
    from kennabot.database import close_db, init_db

    settings = get_settings()
    await init_db(settings)
    typer.echo(f"Database initialized at {settings.db_path}")
    await close_db()


@app.command()
async def migrate() -> None:
    """Apply all pending Alembic migrations (upgrade heads).

    Equivalent to running ``alembic upgrade heads`` from the command line.
    Version directories are automatically discovered from enabled plugins.
    """
    import asyncio
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from kennabot.config import get_settings

    settings = get_settings()
    ini_path = Path(__file__).parent.parent.parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.db_url)

    typer.echo("Running migrations...")
    await asyncio.to_thread(command.upgrade, alembic_cfg, "heads")
    typer.echo("Migrations applied.")


@app.command()
async def revision(
    message: Annotated[
        str, typer.Option("--message", "-m", help="Short description of the migration.")
    ] = "new migration",
    autogenerate: Annotated[
        bool, typer.Option("--autogenerate", help="Auto-detect schema changes.")
    ] = False,
    plugin: Annotated[
        str | None,
        typer.Option(
            "--plugin",
            "-p",
            help=(
                "Plugin name to write the migration into "
                "(e.g. 'plusplus'). Omit to write a core migration."
            ),
        ),
    ] = None,
) -> None:
    """Generate a new Alembic migration script.

    Use --plugin <name> to write the migration into that plugin's
    migrations/versions/ directory.  Omit --plugin for core migrations.

    Examples:

    \b
        kennabot db revision -m "add widget table" --plugin plusplus --autogenerate
        kennabot db revision -m "add core setting"
    """
    import asyncio
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from kennabot.config import get_settings

    settings = get_settings()
    ini_path = Path(__file__).parent.parent.parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.db_url)

    # Build kwargs for alembic.command.revision
    kwargs: dict = {"message": message, "autogenerate": autogenerate}

    if plugin:
        # Resolve plugin-specific version directory
        plugins_dir = Path(__file__).parent.parent / "plugins"
        plugin_versions = plugins_dir / plugin / "migrations" / "versions"
        if not plugin_versions.is_dir():
            typer.echo(
                f"Error: no migrations/versions/ directory found for plugin '{plugin}'.\n"
                f"Expected: {plugin_versions}",
                err=True,
            )
            raise typer.Exit(code=1)
        kwargs["version_path"] = str(plugin_versions)
        kwargs["branch_label"] = plugin
        kwargs["head"] = f"{plugin}@head"

    await asyncio.to_thread(command.revision, alembic_cfg, **kwargs)
