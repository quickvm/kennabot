"""Name parsing, validation, and formatting helpers for the PlusPlus plugin."""

from __future__ import annotations

import re

# Regex for matching plusplus/minusminus patterns in messages.
#
# Matches these forms:
#   <@U12345>++                      Slack user mention increment
#   <@U12345>-- or <@U12345>—        Slack user mention decrement (-- or em-dash)
#   thing++                          Arbitrary thing increment
#   thing--                          Arbitrary thing decrement
#   <@U12345>++ for being awesome    With reason
#   thing-- because reasons          With reason
#   ++ or -- or —                    Bare (MRU, most recently used)
#
# Group 1: Slack user ID from <@U12345> mention (optional)
# Group 2: Plain text name like "pizza" or "@alice" (optional)
# Group 3: The operator: ++, --, or — (em-dash)
# Group 4: The reason text (optional, after conjunction)
#
# Note: Groups 1 and 2 are mutually exclusive. If both are None, it's a bare ++/--.
PLUSPLUS_PATTERN = re.compile(
    r"^"
    r"(?:"
    r"(?:<@(\w+)>)"  # Group 1: Slack user mention <@U12345>
    r"|"
    r"([\"']?.+?[\"']?)"  # Group 2: plain name (thing, @user, "multi word", etc.)
    r")?"  # The entire name part is optional (for bare ++/--)
    r"\s*"
    r"(\+\+|--|—)"  # Group 3: operator
    r"(?:"
    r"\s+(?:{conjunctions})\s+"  # conjunction keyword
    r"(.+)"  # Group 4: reason
    r")?"
    r"$",
    re.IGNORECASE,
)

# Default conjunction words — will be replaced at runtime with config values
DEFAULT_CONJUNCTIONS = ["for", "because", "cause", "cuz", "as"]


def build_pattern(conjunctions: list[str] | None = None) -> re.Pattern[str]:
    """Build the plusplus regex pattern with the given conjunctions.

    Args:
        conjunctions: List of conjunction words. Defaults to DEFAULT_CONJUNCTIONS.

    Returns:
        Compiled regex pattern.
    """
    conj = conjunctions or DEFAULT_CONJUNCTIONS
    conj_pattern = "|".join(re.escape(c) for c in conj)

    return re.compile(
        r"^"
        r"(?:"
        r"(?:<@(\w+)>)"  # Group 1: Slack user mention
        r"|"
        r"""([^\+\-\—][^\+\-\—]*?)"""  # Group 2: plain text name
        r")?"  # Name part is optional (bare ++/--)
        r"\s*"
        r"(\+\+|--|—)"  # Group 3: operator
        r"(?:"
        rf"\s+(?:{conj_pattern})\s+"  # conjunction
        r"(.+)"  # Group 4: reason
        r")?"
        r"$",
        re.IGNORECASE,
    )


def normalize_name(name: str) -> str:
    """Normalize an entity name for consistent storage and lookup.

    - Strip leading @ symbols
    - Strip surrounding quotes
    - Strip trailing commas, colons, whitespace
    - Lowercase everything

    Args:
        name: Raw name from message text.

    Returns:
        Normalized name string.
    """
    name = name.strip()
    # Remove surrounding quotes
    if (name.startswith('"') and name.endswith('"')) or (
        name.startswith("'") and name.endswith("'")
    ):
        name = name[1:-1]
    # Strip leading @
    name = name.lstrip("@")
    # Strip trailing punctuation
    name = name.rstrip(",:;. ")
    # Lowercase
    name = name.lower()
    return name


def normalize_reason(reason: str) -> str:
    """Normalize a reason string for consistent storage.

    Args:
        reason: Raw reason text.

    Returns:
        Normalized reason string.
    """
    return reason.strip().lower()


def format_score_message(
    name: str,
    display_name: str,
    total_score: int,
    delta: int,
    reason: str | None = None,
    reason_score: int | None = None,
) -> str:
    """Format the response message after a score change.

    Args:
        name: Normalized entity name.
        display_name: Display name (may include Slack mention formatting).
        total_score: New total score.
        delta: The change (+1 or -1).
        reason: Optional reason text.
        reason_score: Score for this specific reason (if reason given).

    Returns:
        Formatted message string.
    """
    points_word = "point" if abs(total_score) == 1 else "points"
    delta_str = f"+{delta}" if delta > 0 else str(delta)

    msg = f"{display_name} has {total_score} {points_word} ({delta_str})."

    if reason and reason_score is not None:
        reason_points_word = "point" if abs(reason_score) == 1 else "points"
        is_word = "is" if abs(reason_score) == 1 else "are"
        msg += f" {reason_score} {reason_points_word} {is_word} for {reason}."

    return msg


def format_leaderboard(
    entries: list[tuple[str, int]],
    title: str = "Top scores",
) -> str:
    """Format a leaderboard for display.

    Args:
        entries: List of (name, score) tuples, already sorted.
        title: Title for the leaderboard.

    Returns:
        Formatted leaderboard string.
    """
    if not entries:
        return f"*{title}*\nNo scores yet!"

    lines = [f"*{title}*"]
    for i, (name, score) in enumerate(entries, 1):
        points_word = "point" if abs(score) == 1 else "points"
        lines.append(f"{i}. {name} — {score} {points_word}")

    return "\n".join(lines)


def format_score_detail(
    display_name: str,
    total_score: int,
    reasons: list[tuple[str, int]],
) -> str:
    """Format a detailed score view for a single entity.

    Args:
        display_name: Display name of the entity.
        total_score: Total score.
        reasons: List of (reason, points) tuples, sorted by points descending.

    Returns:
        Formatted detail string.
    """
    points_word = "point" if abs(total_score) == 1 else "points"
    lines = [f"*{display_name}* has {total_score} {points_word}."]

    if reasons:
        lines.append("Top reasons:")
        for reason, points in reasons[:10]:  # Show top 10 reasons
            lines.append(f"  {reason}: {points}")

    return "\n".join(lines)
