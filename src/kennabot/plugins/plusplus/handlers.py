"""Slack event handlers for the PlusPlus plugin.

Contains the message listener and /plusplus slash command handler.
These are registered on the Bolt app by the PlusPlusPlugin.register() method.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, cast

from kennabot.plugins.plusplus import scorekeeper
from kennabot.plugins.plusplus.helpers import (
    build_pattern,
    format_leaderboard,
    format_score_detail,
    format_score_message,
    normalize_name,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from kennabot.config import Settings

logger = logging.getLogger(__name__)


class PlusPlusHandlers:
    """Container for PlusPlus event handler methods.

    Holds references to the session factory and settings so the handler
    functions can access them via closure.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings):
        self.session_factory = session_factory
        self.settings = settings
        self.pattern = build_pattern(settings.reason_conjunctions)

    async def handle_message(self, message: dict, say, client) -> None:
        """Handle incoming messages and check for ++/-- patterns.

        This is registered as a message listener on the Bolt app. It receives
        every message and checks if it matches the plusplus pattern.
        """
        text = message.get("text", "")
        if not text:
            return

        # Skip bot messages and message edits
        if message.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
            return

        logger.debug(f"Processing message: {text}")

        match = self.pattern.match(text.strip())
        if not match:
            logger.debug(f"No match for: {text.strip()}")
            return

        logger.debug(f"Matched! Groups: {match.groups()}")

        slack_user_id_match = match.group(1)  # From <@U12345> mention
        plain_name = match.group(2)  # From plain text
        operator = match.group(3)  # ++ or -- or —
        reason = match.group(4)  # Optional reason

        from_user_id = message.get("user", "")
        channel_id = message.get("channel", "")
        thread_ts = message.get("thread_ts")
        # A message is a thread reply if it has thread_ts (the parent ts)
        is_in_thread = thread_ts is not None

        if not from_user_id:
            return

        # Look up the voter's username for self-vote detection
        from_user_name: str | None = None
        try:
            from_user_info = await client.users_info(user=from_user_id)
            from_user_name = from_user_info["user"].get("name")
        except Exception:
            logger.debug("Failed to look up voter username for %s", from_user_id)

        # Determine the target name and whether it's a Slack user
        is_user = False
        target_slack_user_id: str | None = None
        display_name: str

        if slack_user_id_match:
            # It's a <@U12345> mention
            is_user = True
            target_slack_user_id = slack_user_id_match
            # Look up name based on settings
            try:
                user_info = await client.users_info(user=slack_user_id_match)
                if self.settings.use_display_name:
                    display_name = (
                        user_info["user"].get("real_name")
                        or user_info["user"].get("name")
                        or slack_user_id_match
                    )
                else:
                    display_name = (
                        user_info["user"].get("name")
                        or user_info["user"].get("real_name")
                        or slack_user_id_match
                    )
                name = normalize_name(display_name)
            except Exception:
                logger.warning("Failed to look up user %s", slack_user_id_match)
                name = slack_user_id_match.lower()
                display_name = f"<@{slack_user_id_match}>"
        elif plain_name:
            # It's a plain text name like "pizza" or "@alice"
            name = normalize_name(plain_name)
            display_name = name
            if not name:
                return
        else:
            # Bare ++ or -- : use MRU (thread-aware if in a thread)
            # Try thread MRU first, fall back to channel MRU
            last = None
            if is_in_thread:
                last = scorekeeper.get_last(channel_id, thread_ts)
            if last is None:
                last = scorekeeper.get_last(channel_id)
            if last is None:
                return  # No MRU for this channel/thread, silently ignore
            name, last_reason = last
            display_name = name
            # If no new reason provided, reuse the last reason
            if not reason and last_reason:
                reason = last_reason

        logger.debug(
            "Resolved: name=%s, operator=%s, reason=%s, is_thread=%s, thread_ts=%s",
            name,
            operator,
            reason,
            is_in_thread,
            thread_ts,
        )

        # Determine operation
        if operator == "++":
            result = await scorekeeper.add(
                self.session_factory,
                name=name,
                from_user_id=from_user_id,
                channel_id=channel_id,
                reason=reason,
                is_user=is_user,
                slack_user_id=target_slack_user_id,
                cooldown_seconds=self.settings.cooldown_seconds,
                thread_ts=thread_ts if is_in_thread else None,
                from_user_name=from_user_name,
            )
        else:
            # -- or — (em-dash)
            result = await scorekeeper.subtract(
                self.session_factory,
                name=name,
                from_user_id=from_user_id,
                channel_id=channel_id,
                reason=reason,
                is_user=is_user,
                slack_user_id=target_slack_user_id,
                cooldown_seconds=self.settings.cooldown_seconds,
                thread_ts=thread_ts if is_in_thread else None,
                from_user_name=from_user_name,
            )

        if not result.success:
            if result.error == "self_vote":
                await say(f"Nice try, <@{from_user_id}>. You can't give yourself points.")
            elif result.error == "spam":
                # Silently ignore spam
                pass
            elif result.error == "empty_name":
                pass
            return

        # Format and send the response (use Slack mention format for user targets)
        display = f"<@{target_slack_user_id}>" if is_user and target_slack_user_id else display_name

        msg = format_score_message(
            name=result.name,
            display_name=display,
            total_score=result.total_score,
            delta=result.delta,
            reason=result.reason,
            reason_score=result.reason_score,
        )
        # Reply in thread if this is a thread reply
        if is_in_thread:
            await say(msg, thread_ts=thread_ts)
        else:
            await say(msg)

    async def handle_slash_command(self, ack, body, respond, client) -> None:
        """Handle the /plusplus slash command.

        Subcommands:
            /plusplus @user          Show score for a user
            /plusplus thing          Show score for a thing
            /plusplus top [N]        Show top N scores
            /plusplus bottom [N]     Show bottom N scores
            /plusplus erase <name> [for <reason>]  Admin-only erase
            /plusplus                Show help
        """
        await ack()

        text = (body.get("text") or "").strip()
        user_id = body.get("user_id", "")

        if not text:
            await respond(self._help_text())
            return

        # Parse subcommand
        parts: list[str] = cast(list[str], text.split(None, 1))
        subcommand = parts[0].lower()

        if subcommand in ("top", "bottom"):
            await self._handle_leaderboard(respond, subcommand, parts)
        elif subcommand == "erase":
            await self._handle_erase(respond, user_id, parts)
        elif subcommand == "help":
            await respond(self._help_text())
        else:
            # Treat the entire text as a name to look up
            await self._handle_score_lookup(respond, text, client)

    async def _handle_score_lookup(self, respond, text: str, client) -> None:
        """Look up the score for a user or thing."""
        # Check if it's a Slack user mention <@U12345>
        user_mention = re.match(r"<@(\w+)(?:\|[^>]*)?>", text)
        if user_mention:
            slack_user_id = user_mention.group(1)
            try:
                user_info = await client.users_info(user=slack_user_id)
                display_name = (
                    user_info["user"].get("real_name")
                    or user_info["user"].get("name")
                    or slack_user_id
                )
                name = normalize_name(display_name)
            except Exception:
                name = slack_user_id.lower()
                display_name = f"<@{slack_user_id}>"
        else:
            name = normalize_name(text)
            display_name = name

        result = await scorekeeper.get_score(self.session_factory, name)

        if result is None:
            await respond(f"No score found for *{display_name}*.")
            return

        total_score, reasons = result
        msg = format_score_detail(display_name, total_score, reasons)
        await respond(msg)

    async def _handle_leaderboard(self, respond, direction: str, parts: list[str]) -> None:
        """Handle /plusplus top [N] and /plusplus bottom [N]."""
        n = 10  # default
        if len(parts) > 1:
            try:
                n = int(parts[1])
                n = max(1, min(n, 50))  # Clamp between 1 and 50
            except ValueError:
                await respond(f"Invalid number: `{parts[1]}`. Usage: `/plusplus {direction} [N]`")
                return

        if direction == "top":
            entries = await scorekeeper.top(self.session_factory, n)
            title = f"Top {len(entries)}"
        else:
            entries = await scorekeeper.bottom(self.session_factory, n)
            title = f"Bottom {len(entries)}"

        msg = format_leaderboard(entries, title=title)
        await respond(msg)

    async def _handle_erase(self, respond, user_id: str, parts: list[str]) -> None:
        """Handle /plusplus erase <name> [for <reason>].

        Admin-only if admin_users is configured.
        """
        if self.settings.admin_users and user_id not in self.settings.admin_users:
            await respond("You don't have permission to erase scores.")
            return

        if len(parts) < 2 or not parts[1].strip():
            await respond("Usage: `/plusplus erase <name> [for <reason>]`")
            return

        erase_text = parts[1].strip()

        # Check for "name for reason" pattern
        reason: str | None = None
        conj_pattern = "|".join(re.escape(c) for c in self.settings.reason_conjunctions)
        reason_match = re.match(
            rf"^(.+?)\s+(?:{conj_pattern})\s+(.+)$",
            erase_text,
            re.IGNORECASE,
        )

        if reason_match:
            target_name = reason_match.group(1).strip()
            reason = reason_match.group(2).strip()
        else:
            target_name = erase_text

        # Normalize the target name (handles <@U12345> mentions too)
        target_name = normalize_name(target_name)

        erased = await scorekeeper.erase(self.session_factory, target_name, reason)

        if erased:
            if reason:
                await respond(f"Erased reason *{reason}* from *{target_name}*.")
            else:
                await respond(f"Erased all scores for *{target_name}*.")
        else:
            if reason:
                await respond(f"No reason *{reason}* found for *{target_name}*.")
            else:
                await respond(f"No scores found for *{target_name}*.")

    @staticmethod
    def _help_text() -> str:
        """Return the help text for the /plusplus slash command."""
        return (
            "*PlusPlus — Karma tracking for Slack*\n\n"
            "*Inline usage (in any message):*\n"
            "`@user++` or `thing++` — Add a point\n"
            "`@user--` or `thing--` — Remove a point\n"
            "`@user++ for <reason>` — Add a point with a reason\n"
            "`++` or `--` — Apply to the last voted thing in this channel\n\n"
            "*Slash commands:*\n"
            "`/plusplus @user` or `/plusplus thing` — Check score\n"
            "`/plusplus top [N]` — Show top scores (default 10)\n"
            "`/plusplus bottom [N]` — Show bottom scores\n"
            "`/plusplus erase <name> [for <reason>]` — Erase scores (admin only)\n"
            "`/plusplus help` — Show this help message"
        )
