"""Score business logic for the PlusPlus plugin.

Handles adding/subtracting points, querying scores, leaderboards,
spam prevention, self-vote prevention, and MRU tracking.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select

from kennabot.plugins.plusplus.helpers import normalize_name, normalize_reason
from kennabot.plugins.plusplus.models import Score, ScoreLog, ScoreReason

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ScoreResult:
    """Result of a score change operation."""

    def __init__(
        self,
        *,
        success: bool,
        name: str = "",
        total_score: int = 0,
        delta: int = 0,
        reason: str | None = None,
        reason_score: int | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.name = name
        self.total_score = total_score
        self.delta = delta
        self.reason = reason
        self.reason_score = reason_score
        self.error = error


# In-memory MRU cache: channel_id -> (name, reason)
# This is intentionally not persisted — it resets on bot restart,
# which is fine since MRU is a convenience feature.
# Key is "channel_id" or "channel_id:thread_ts" for thread-specific MRU
_mru_cache: dict[str, tuple[str, str | None]] = {}


def _mru_key(channel_id: str, thread_ts: str | None = None) -> str:
    """Generate MRU key. If thread_ts is provided, use thread-specific MRU."""
    if thread_ts:
        return f"{channel_id}:{thread_ts}"
    return channel_id


def get_last(channel_id: str, thread_ts: str | None = None) -> tuple[str, str | None] | None:
    """Get the most recently used target for a channel or thread.

    Returns:
        Tuple of (name, reason) or None if no recent vote in this channel/thread.
    """
    return _mru_cache.get(_mru_key(channel_id, thread_ts))


def set_last(
    channel_id: str,
    name: str,
    reason: str | None = None,
    thread_ts: str | None = None,
) -> None:
    """Record the most recently used target for a channel or thread."""
    _mru_cache[_mru_key(channel_id, thread_ts)] = (name, reason)


async def _is_spam(
    session: AsyncSession,
    from_user_id: str,
    to_name: str,
    cooldown_seconds: int,
) -> bool:
    """Check if this vote would be spam (same voter -> same target within cooldown)."""
    cutoff = datetime.now(UTC) - timedelta(seconds=cooldown_seconds)
    stmt = (
        select(ScoreLog)
        .where(ScoreLog.from_user_id == from_user_id)
        .where(ScoreLog.to_name == to_name)
        .where(ScoreLog.created_at > cutoff)
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first() is not None


async def _get_or_create_score(
    session: AsyncSession,
    name: str,
    is_user: bool = False,
    slack_user_id: str | None = None,
) -> Score:
    """Get an existing score record or create a new one."""
    stmt = select(Score).where(Score.name == name)
    result = await session.execute(stmt)
    score = result.scalars().first()

    if score is None:
        score = Score(
            name=name,
            score=0,
            is_user=is_user,
            slack_user_id=slack_user_id,
        )
        session.add(score)
        await session.flush()

    return score


async def _get_or_create_reason(
    session: AsyncSession,
    score_id: int,
    reason: str,
) -> ScoreReason:
    """Get an existing reason record or create a new one."""
    stmt = (
        select(ScoreReason)
        .where(ScoreReason.score_id == score_id)
        .where(ScoreReason.reason == reason)
    )
    result = await session.execute(stmt)
    score_reason = result.scalars().first()

    if score_reason is None:
        score_reason = ScoreReason(
            score_id=score_id,
            reason=reason,
            points=0,
        )
        session.add(score_reason)
        await session.flush()

    return score_reason


async def add(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    from_user_id: str,
    channel_id: str,
    reason: str | None = None,
    is_user: bool = False,
    slack_user_id: str | None = None,
    cooldown_seconds: int = 5,
    thread_ts: str | None = None,
    from_user_name: str | None = None,
) -> ScoreResult:
    """Add a point to an entity.

    Args:
        session_factory: Async session factory.
        name: Normalized name of the target.
        from_user_id: Slack user ID of the voter.
        channel_id: Slack channel where the vote occurred.
        reason: Optional reason text.
        is_user: Whether the target is a Slack user.
        slack_user_id: Slack user ID of the target (if is_user).
        cooldown_seconds: Spam prevention cooldown.
        from_user_name: Slack username of the voter (for self-vote detection).

    Returns:
        ScoreResult with the outcome.
    """
    return await _change_score(
        session_factory,
        name=name,
        from_user_id=from_user_id,
        channel_id=channel_id,
        delta=1,
        reason=reason,
        is_user=is_user,
        slack_user_id=slack_user_id,
        cooldown_seconds=cooldown_seconds,
        thread_ts=thread_ts,
        from_user_name=from_user_name,
    )


async def subtract(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    from_user_id: str,
    channel_id: str,
    reason: str | None = None,
    is_user: bool = False,
    slack_user_id: str | None = None,
    cooldown_seconds: int = 5,
    thread_ts: str | None = None,
    from_user_name: str | None = None,
) -> ScoreResult:
    """Remove a point from an entity.

    Args:
        session_factory: Async session factory.
        name: Normalized name of the target.
        from_user_id: Slack user ID of the voter.
        channel_id: Slack channel where the vote occurred.
        reason: Optional reason text.
        is_user: Whether the target is a Slack user.
        slack_user_id: Slack user ID of the target (if is_user).
        cooldown_seconds: Spam prevention cooldown.
        from_user_name: Slack username of the voter (for self-vote detection).

    Returns:
        ScoreResult with the outcome.
    """
    return await _change_score(
        session_factory,
        name=name,
        from_user_id=from_user_id,
        channel_id=channel_id,
        delta=-1,
        reason=reason,
        is_user=is_user,
        slack_user_id=slack_user_id,
        cooldown_seconds=cooldown_seconds,
        thread_ts=thread_ts,
        from_user_name=from_user_name,
    )


async def _change_score(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    from_user_id: str,
    channel_id: str,
    delta: int,
    reason: str | None = None,
    is_user: bool = False,
    slack_user_id: str | None = None,
    cooldown_seconds: int = 5,
    thread_ts: str | None = None,
    from_user_name: str | None = None,
) -> ScoreResult:
    """Core score change logic shared by add() and subtract()."""
    name = normalize_name(name)
    norm_reason = normalize_reason(reason) if reason else None

    if not name:
        return ScoreResult(success=False, error="empty_name")

    # Self-vote prevention (both increment and decrement)
    # Check by Slack user ID (for @mentions)
    if is_user and slack_user_id and slack_user_id == from_user_id:
        return ScoreResult(
            success=False,
            name=name,
            error="self_vote",
        )
    # Check by username (for plain text like "andy++")
    if from_user_name and normalize_name(from_user_name) == name:
        return ScoreResult(
            success=False,
            name=name,
            error="self_vote",
        )

    async with session_factory() as session, session.begin():
        # Spam check
        if await _is_spam(session, from_user_id, name, cooldown_seconds):
            return ScoreResult(success=False, name=name, error="spam")

        # Get or create the score entry
        score = await _get_or_create_score(
            session, name, is_user=is_user, slack_user_id=slack_user_id
        )
        assert score.id is not None

        # Update total score
        score.score += delta
        score.updated_at = datetime.now(UTC)

        # Update reason score if provided
        reason_score = None
        if norm_reason:
            score_reason = await _get_or_create_reason(
                session,
                score.id,
                norm_reason,
            )
            score_reason.points += delta
            reason_score = score_reason.points

        # Log the vote
        direction = "++" if delta > 0 else "--"
        log_entry = ScoreLog(
            from_user_id=from_user_id,
            to_name=name,
            direction=direction,
            reason=norm_reason,
            channel_id=channel_id,
        )
        session.add(log_entry)

    # Update MRU (outside the db transaction)
    # Only set channel MRU if NOT in a thread; thread votes stay scoped to the thread
    if thread_ts:
        set_last(channel_id, name, norm_reason, thread_ts)
    else:
        set_last(channel_id, name, norm_reason)

    return ScoreResult(
        success=True,
        name=name,
        total_score=score.score,
        delta=delta,
        reason=norm_reason,
        reason_score=reason_score,
    )


async def get_score(
    session_factory: async_sessionmaker[AsyncSession],
    name: str,
) -> tuple[int, list[tuple[str, int]]] | None:
    """Get the total score and reasons for an entity.

    Args:
        session_factory: Async session factory.
        name: Normalized name of the entity.

    Returns:
        Tuple of (total_score, [(reason, points), ...]) sorted by points desc,
        or None if the entity has never been scored.
    """
    name = normalize_name(name)

    async with session_factory() as session:
        stmt = select(Score).where(Score.name == name)
        result = await session.execute(stmt)
        score = result.scalars().first()

        if score is None:
            return None

        # Fetch reasons
        reason_stmt = (
            select(ScoreReason)
            .where(ScoreReason.score_id == score.id)
            .order_by(text("points DESC"))
        )
        reason_result = await session.execute(reason_stmt)
        reasons = [(r.reason, r.points) for r in reason_result.scalars().all()]

        return score.score, reasons


async def top(
    session_factory: async_sessionmaker[AsyncSession],
    n: int = 10,
) -> list[tuple[str, int]]:
    """Get the top N scores.

    Args:
        session_factory: Async session factory.
        n: Number of entries to return.

    Returns:
        List of (name, score) tuples sorted by score descending.
    """
    async with session_factory() as session:
        stmt = select(Score).order_by(text("score DESC")).limit(n)
        result = await session.execute(stmt)
        return [(s.name, s.score) for s in result.scalars().all()]


async def bottom(
    session_factory: async_sessionmaker[AsyncSession],
    n: int = 10,
) -> list[tuple[str, int]]:
    """Get the bottom N scores.

    Args:
        session_factory: Async session factory.
        n: Number of entries to return.

    Returns:
        List of (name, score) tuples sorted by score ascending.
    """
    async with session_factory() as session:
        stmt = select(Score).order_by(text("score ASC")).limit(n)
        result = await session.execute(stmt)
        return [(s.name, s.score) for s in result.scalars().all()]


async def set_score(
    session_factory: async_sessionmaker[AsyncSession],
    name: str,
    points: int,
) -> tuple[int, int]:
    """Manually set the total score for an entity.

    Creates the entity if it doesn't exist.

    Args:
        session_factory: Async session factory.
        name: Normalized name of the entity.
        points: The new score value.

    Returns:
        Tuple of (old_score, new_score).
    """
    name = normalize_name(name)

    async with session_factory() as session, session.begin():
        score = await _get_or_create_score(session, name)
        old = score.score
        score.score = points
        score.updated_at = datetime.now(UTC)

    return old, points


async def erase(
    session_factory: async_sessionmaker[AsyncSession],
    name: str,
    reason: str | None = None,
) -> bool:
    """Erase a score entry or a specific reason.

    If reason is provided, only that reason is removed (total score unchanged).
    If reason is None, the entire score entry and all reasons are deleted.

    Args:
        session_factory: Async session factory.
        name: Normalized name of the entity.
        reason: Optional specific reason to erase.

    Returns:
        True if something was erased, False if nothing was found.
    """
    name = normalize_name(name)
    norm_reason = normalize_reason(reason) if reason else None

    async with session_factory() as session, session.begin():
        stmt = select(Score).where(Score.name == name)
        result = await session.execute(stmt)
        score = result.scalars().first()

        if score is None:
            return False

        if norm_reason:
            # Erase only the specific reason
            reason_stmt = (
                select(ScoreReason)
                .where(ScoreReason.score_id == score.id)
                .where(ScoreReason.reason == norm_reason)
            )
            reason_result = await session.execute(reason_stmt)
            score_reason = reason_result.scalars().first()

            if score_reason is None:
                return False

            await session.delete(score_reason)
        else:
            # Erase the entire entity
            await session.delete(score)

    return True
