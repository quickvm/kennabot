"""KennaBot CLI — management interface built with Typer.

This is the main entry point registered as ``kennabot`` in pyproject.toml.
"""

from __future__ import annotations

import typer

from kennabot import __version__
from kennabot.cli.async_typer import AsyncTyper
from kennabot.cli.config_cmd import app as config_app
from kennabot.cli.db import app as db_app
from kennabot.cli.healthcheck import healthcheck
from kennabot.cli.plugin_cmd import app as plugin_app
from kennabot.cli.serve import serve

app = AsyncTyper(
    name="kennabot",
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="KennaBot — a modern Slack bot management CLI.",
)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """KennaBot — a modern Slack bot."""
    if version:
        typer.echo(f"kennabot {__version__}")
        raise typer.Exit()


# --- Core commands ---
app.command()(serve)
app.command()(healthcheck)

# --- Core command groups ---
app.add_typer(db_app, name="db")
app.add_typer(config_app, name="config")
app.add_typer(plugin_app, name="plugin")


# --- Plugin CLI registration ---
def _register_plugin_clis() -> None:
    """Discover plugins and let each register its CLI subcommands."""
    from kennabot.plugins import discover_plugins

    for plugin_cls in discover_plugins():
        try:
            plugin = plugin_cls()
            plugin.register_cli(app)
        except Exception:  # noqa: BLE001
            # Don't let a broken plugin CLI prevent the rest of the CLI from working
            pass


_register_plugin_clis()
