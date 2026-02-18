"""The ``kennabot config`` command group — configuration inspection."""

from __future__ import annotations

import typer

from kennabot.cli.async_typer import AsyncTyper

app = AsyncTyper(name="config", help="Configuration inspection and validation.")


def _redact(token: str, visible: int = 8) -> str:
    """Show the first ``visible`` characters of a token, then '...'."""
    if len(token) <= visible:
        return token
    return token[:visible] + "..."


@app.command()
def show() -> None:
    """Display the current configuration (tokens redacted)."""
    from kennabot.config import get_settings

    settings = get_settings()

    typer.echo("KennaBot Configuration")
    typer.echo("=" * 40)
    typer.echo(f"  SLACK_BOT_TOKEN:             {_redact(settings.slack_bot_token)}")
    typer.echo(f"  SLACK_APP_TOKEN:             {_redact(settings.slack_app_token)}")
    typer.echo(f"  DB_PATH:                     {settings.db_path}")
    typer.echo(f"  ADMIN_USERS:                 {settings.admin_users or '(none)'}")
    typer.echo(f"  COOLDOWN_SECONDS:            {settings.cooldown_seconds}")
    typer.echo(f"  REASON_CONJUNCTIONS:         {', '.join(settings.reason_conjunctions)}")
    typer.echo(f"  LOG_LEVEL:                   {settings.log_level}")


@app.command()
async def validate() -> None:
    """Validate configuration: check token formats, DB path, and Slack connectivity."""
    from pathlib import Path

    from kennabot.config import get_settings

    settings = get_settings()
    all_ok = True

    # --- Token format checks ---
    if settings.slack_bot_token.startswith("xoxb-"):
        typer.echo("[OK]  SLACK_BOT_TOKEN has valid prefix (xoxb-)")
    else:
        typer.echo("[FAIL] SLACK_BOT_TOKEN should start with 'xoxb-'")
        all_ok = False

    if settings.slack_app_token.startswith("xapp-"):
        typer.echo("[OK]  SLACK_APP_TOKEN has valid prefix (xapp-)")
    else:
        typer.echo("[FAIL] SLACK_APP_TOKEN should start with 'xapp-'")
        all_ok = False

    # --- DB path check ---
    db_dir = Path(settings.db_path).parent
    if db_dir.exists():
        typer.echo(f"[OK]  Database directory exists: {db_dir}")
    else:
        typer.echo(f"[WARN] Database directory does not exist (will be created): {db_dir}")

    # --- Slack API connectivity ---
    typer.echo("       Checking Slack API connectivity...")
    try:
        from slack_sdk.web.async_client import AsyncWebClient

        client = AsyncWebClient(token=settings.slack_bot_token)
        response = await client.auth_test()

        if response.get("ok"):
            bot_name = response.get("user", "unknown")
            team = response.get("team", "unknown")
            typer.echo(f"[OK]  Slack API: authenticated as @{bot_name} in {team}")
        else:
            typer.echo(f"[FAIL] Slack API: {response.get('error', 'unknown error')}")
            all_ok = False
    except Exception as exc:
        typer.echo(f"[FAIL] Slack API: {exc}")
        all_ok = False

    # --- Summary ---
    typer.echo("")
    if all_ok:
        typer.echo("All checks passed.")
    else:
        typer.echo("Some checks failed. Review the output above.")
        raise typer.Exit(code=1)
