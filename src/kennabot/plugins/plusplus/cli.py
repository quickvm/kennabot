"""CLI commands for the PlusPlus plugin.

Registered under ``kennabot plusplus`` by PlusPlusPlugin.register_cli().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kennabot.cli.async_typer import AsyncTyper


def create_plusplus_cli() -> AsyncTyper:
    """Create and return the PlusPlus CLI sub-application."""
    pp_app = AsyncTyper(
        name="plusplus",
        help="PlusPlus karma tracking — manage scores from the command line.",
    )

    @pp_app.command()
    async def get(
        name: str = typer.Argument(help="Name of the user or thing to look up."),
    ) -> None:
        """Look up the score and reasons for a user or thing."""
        session_factory = await _init_db()
        from kennabot.plugins.plusplus import scorekeeper

        result = await scorekeeper.get_score(session_factory, name)
        await _close()

        if result is None:
            typer.echo(f"No score found for '{name}'.")
            raise typer.Exit(code=1)

        total, reasons = result
        points_word = "point" if abs(total) == 1 else "points"
        typer.echo(f"{name}: {total} {points_word}")
        if reasons:
            typer.echo("Reasons:")
            for reason, pts in reasons[:20]:
                typer.echo(f"  {reason}: {pts}")

    @pp_app.command()
    async def top(
        limit: int = typer.Option(10, "--limit", "-n", help="Number of entries to show."),
    ) -> None:
        """Show the top scores."""
        session_factory = await _init_db()
        from kennabot.plugins.plusplus import scorekeeper

        entries = await scorekeeper.top(session_factory, limit)
        await _close()

        if not entries:
            typer.echo("No scores yet.")
            return

        typer.echo(f"Top {len(entries)}")
        typer.echo("-" * 35)
        for i, (entry_name, score) in enumerate(entries, 1):
            points_word = "point" if abs(score) == 1 else "points"
            typer.echo(f"  {i:>3}. {entry_name:<20} {score} {points_word}")

    @pp_app.command()
    async def bottom(
        limit: int = typer.Option(10, "--limit", "-n", help="Number of entries to show."),
    ) -> None:
        """Show the bottom scores."""
        session_factory = await _init_db()
        from kennabot.plugins.plusplus import scorekeeper

        entries = await scorekeeper.bottom(session_factory, limit)
        await _close()

        if not entries:
            typer.echo("No scores yet.")
            return

        typer.echo(f"Bottom {len(entries)}")
        typer.echo("-" * 35)
        for i, (entry_name, score) in enumerate(entries, 1):
            points_word = "point" if abs(score) == 1 else "points"
            typer.echo(f"  {i:>3}. {entry_name:<20} {score} {points_word}")

    @pp_app.command("set")
    async def set_score(
        name: str = typer.Argument(help="Name of the user or thing."),
        points: int = typer.Argument(help="Score value to set."),
        force: bool = typer.Option(
            False, "--force", "-f", help="Required to confirm the score change."
        ),
    ) -> None:
        """Manually set a score to an exact value.

        This is an admin tool for correcting data. Requires --force.
        """
        if not force:
            typer.echo("This command directly modifies score data.")
            typer.echo(f"To set '{name}' to {points}, re-run with --force:")
            typer.echo(f"  kennabot plusplus set '{name}' {points} --force")
            raise typer.Exit(code=1)

        session_factory = await _init_db()
        from kennabot.plugins.plusplus import scorekeeper

        old, new = await scorekeeper.set_score(session_factory, name, points)
        await _close()

        typer.echo(f"{name}: {old} -> {new}")

    @pp_app.command()
    async def erase(
        name: str = typer.Argument(help="Name of the user or thing to erase."),
        reason: str | None = typer.Option(
            None, "--reason", "-r", help="Erase only this specific reason."
        ),
    ) -> None:
        """Erase a score entry or a specific reason."""
        session_factory = await _init_db()
        from kennabot.plugins.plusplus import scorekeeper

        erased = await scorekeeper.erase(session_factory, name, reason)
        await _close()

        if erased:
            if reason:
                typer.echo(f"Erased reason '{reason}' from '{name}'.")
            else:
                typer.echo(f"Erased all scores for '{name}'.")
        else:
            if reason:
                typer.echo(f"No reason '{reason}' found for '{name}'.")
            else:
                typer.echo(f"No scores found for '{name}'.")
            raise typer.Exit(code=1)

    @pp_app.command("import-hubot")
    async def import_hubot(
        redis_url: Annotated[
            str | None,
            typer.Option("--redis-url", help="Redis connection URL (e.g. redis://localhost:6379)."),
        ] = None,
        from_file: Annotated[
            Path | None,
            typer.Option("--from-file", help="Path to a JSON file with the hubot brain dump."),
        ] = None,
        redis_key: Annotated[
            str,
            typer.Option("--redis-key", help="Redis key for the hubot brain."),
        ] = "hubot:storage",
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Show what would be imported without writing."),
        ] = False,
    ) -> None:
        """Import scores from a hubot-plusplus Redis brain dump.

        Provide either --redis-url for a live Redis connection, or --from-file
        for a JSON dump file. The two options are mutually exclusive.
        """
        if not redis_url and not from_file:
            typer.echo("Provide either --redis-url or --from-file.")
            raise typer.Exit(code=1)
        if redis_url and from_file:
            typer.echo("Provide only one of --redis-url or --from-file, not both.")
            raise typer.Exit(code=1)

        # Load brain data
        if redis_url:
            brain_data = _load_from_redis(redis_url, redis_key)
        else:
            brain_data = _load_from_file(from_file)  # type: ignore[arg-type]

        plusplus_data = _extract_plusplus(brain_data)
        scores_data: dict = plusplus_data.get("scores", {})
        reasons_data: dict = plusplus_data.get("reasons", {})

        typer.echo(
            f"Found {len(scores_data)} score entries and {len(reasons_data)} entities with reasons."
        )

        if dry_run:
            typer.echo("=== DRY RUN ===")
            for entry_name, score in sorted(scores_data.items(), key=lambda x: x[1], reverse=True):
                reasons = reasons_data.get(entry_name, {})
                reason_str = f" ({len(reasons)} reasons)" if reasons else ""
                typer.echo(f"  {entry_name}: {score} points{reason_str}")
            typer.echo("=== DRY RUN complete ===")
            return

        # Perform import
        from kennabot.config import get_settings
        from kennabot.database import close_db, get_session_factory, init_db
        from kennabot.plugins.plusplus.models import Score, ScoreReason

        settings = get_settings()
        await init_db(settings)
        session_factory = get_session_factory()

        scores_imported = 0
        reasons_imported = 0

        async with session_factory() as session, session.begin():
            for entry_name, score_value in scores_data.items():
                name_lower = entry_name.lower().strip().lstrip("@")
                if not name_lower:
                    continue

                score_entry = Score(
                    name=name_lower,
                    score=int(score_value),
                    is_user=False,
                    slack_user_id=None,
                )
                session.add(score_entry)
                await session.flush()
                assert score_entry.id is not None
                scores_imported += 1

                entity_reasons = reasons_data.get(entry_name, {})
                for reason_text, reason_points in entity_reasons.items():
                    reason_lower = reason_text.lower().strip()
                    if not reason_lower:
                        continue

                    reason_entry = ScoreReason(
                        score_id=score_entry.id,
                        reason=reason_lower,
                        points=int(reason_points),
                    )
                    session.add(reason_entry)
                    reasons_imported += 1

        typer.echo(f"Import complete: {scores_imported} scores, {reasons_imported} reasons.")
        await close_db()

    @pp_app.command()
    async def stats() -> None:
        """Show database statistics for the plusplus plugin (row counts, file size)."""
        from pathlib import Path

        from sqlalchemy import text

        from kennabot.config import get_settings
        from kennabot.database import close_db, get_session_factory, init_db

        settings = get_settings()
        await init_db(settings)
        session_factory = get_session_factory()

        async with session_factory() as session:
            scores_count = (
                await session.execute(text("SELECT COUNT(*) FROM plugin_plusplus_scores"))
            ).scalar()
            reasons_count = (
                await session.execute(text("SELECT COUNT(*) FROM plugin_plusplus_score_reasons"))
            ).scalar()
            log_count = (
                await session.execute(text("SELECT COUNT(*) FROM plugin_plusplus_score_log"))
            ).scalar()

        db_path = Path(settings.db_path)
        file_size = db_path.stat().st_size if db_path.exists() else 0
        size_str = _format_size(file_size)

        typer.echo("PlusPlus Database Statistics")
        typer.echo("=" * 35)
        typer.echo(f"  Path:          {settings.db_path}")
        typer.echo(f"  File size:     {size_str}")
        typer.echo(f"  Scores:        {scores_count}")
        typer.echo(f"  Reasons:       {reasons_count}")
        typer.echo(f"  Log entries:   {log_count}")

        await close_db()

    @pp_app.command()
    async def export(
        output: Annotated[Path, typer.Option("--output", "-o", help="Output file path.")] = Path(
            "scores.json"
        ),
    ) -> None:
        """Export all plusplus scores and reasons to a JSON file."""
        import json as _json

        from sqlmodel import select

        from kennabot.config import get_settings
        from kennabot.database import close_db, get_session_factory, init_db
        from kennabot.plugins.plusplus.models import Score, ScoreReason

        settings = get_settings()
        await init_db(settings)
        session_factory = get_session_factory()

        scores_dict: dict[str, int] = {}
        reasons_dict: dict[str, dict[str, int]] = {}

        async with session_factory() as session:
            result = await session.execute(select(Score))
            for score in result.scalars().all():
                scores_dict[score.name] = score.score

                reason_stmt = select(ScoreReason).where(ScoreReason.score_id == score.id)
                reason_result = await session.execute(reason_stmt)
                entity_reasons = {}
                for r in reason_result.scalars().all():
                    entity_reasons[r.reason] = r.points
                if entity_reasons:
                    reasons_dict[score.name] = entity_reasons

        data = {
            "scores": scores_dict,
            "reasons": reasons_dict,
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w") as f:
            _json.dump(data, f, indent=2, sort_keys=True)

        typer.echo(
            f"Exported {len(scores_dict)} scores and "
            f"{sum(len(v) for v in reasons_dict.values())} reasons to {output}"
        )

        await close_db()

    return pp_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"


async def _init_db():
    """Initialize the database and return the session factory."""
    from kennabot.config import get_settings
    from kennabot.database import get_session_factory, init_db

    settings = get_settings()
    await init_db(settings)
    return get_session_factory()


async def _close():
    """Close the database connection."""
    from kennabot.database import close_db

    await close_db()


def _load_from_redis(redis_url: str, redis_key: str) -> dict:
    """Load the hubot brain blob from a live Redis instance."""
    try:
        import redis as redis_lib
    except ImportError:
        typer.echo(
            "The 'redis' package is required for live Redis import.\n"
            "Install it with: uv pip install 'kennabot[import]'"
        )
        raise typer.Exit(code=1) from None

    typer.echo(f"Connecting to Redis at {redis_url} ...")
    client = redis_lib.from_url(redis_url, decode_responses=True)

    try:
        client.ping()
    except Exception as exc:
        typer.echo(f"Failed to connect to Redis: {exc}")
        raise typer.Exit(code=1) from None

    raw = client.get(redis_key)
    if raw is None:
        typer.echo(f"Key '{redis_key}' not found in Redis.")
        raise typer.Exit(code=1)

    typer.echo(f"Retrieved {len(raw)} bytes from key '{redis_key}'.")
    return json.loads(raw)


def _load_from_file(filepath: Path) -> dict:
    """Load the hubot brain blob from a JSON file."""
    if not filepath.exists():
        typer.echo(f"File not found: {filepath}")
        raise typer.Exit(code=1)

    typer.echo(f"Loading from file: {filepath}")
    with filepath.open() as f:
        return json.load(f)


def _extract_plusplus(brain_data: dict) -> dict:
    """Extract the plusPlus data from the hubot brain blob."""
    if "plusPlus" in brain_data:
        return brain_data["plusPlus"]
    if "data" in brain_data and "plusPlus" in brain_data["data"]:
        return brain_data["data"]["plusPlus"]
    if "scores" in brain_data and "reasons" in brain_data:
        return brain_data

    typer.echo(
        "Could not find plusPlus data in the brain dump.\n"
        "Expected a 'plusPlus' key at the top level or under 'data'.\n"
        f"Available top-level keys: {list(brain_data.keys())}"
    )
    raise typer.Exit(code=1)
