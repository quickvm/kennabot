"""The ``kennabot plugin`` command group — plugin inspection."""

from __future__ import annotations

import typer

from kennabot.cli.async_typer import AsyncTyper

app = AsyncTyper(name="plugin", help="Plugin management.")


@app.command("list")
def list_plugins() -> None:
    """List all discovered plugins."""
    from kennabot.plugins import discover_plugins
    from kennabot.plugins.base import BasePlugin

    plugin_classes = discover_plugins()

    if not plugin_classes:
        typer.echo("No plugins found.")
        return

    typer.echo("Discovered Plugins")
    typer.echo("=" * 50)

    for cls in plugin_classes:
        plugin = cls()
        # Detect if the plugin overrides register_cli
        has_cli = type(plugin).register_cli is not BasePlugin.register_cli
        cli_tag = " [CLI]" if has_cli else ""
        typer.echo(f"  {plugin.name:<15} {plugin.description}{cli_tag}")
