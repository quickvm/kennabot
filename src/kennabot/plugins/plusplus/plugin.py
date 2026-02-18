"""PlusPlus plugin — registers Slack listeners and CLI commands for karma tracking."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from kennabot.plugins.base import BasePlugin
from kennabot.plugins.plusplus.handlers import PlusPlusHandlers

if TYPE_CHECKING:
    from slack_bolt.async_app import AsyncApp
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from kennabot.config import Settings

logger = logging.getLogger(__name__)


class PlusPlusPlugin(BasePlugin):
    """Karma/point tracking system for Slack.

    Allows users to give or take points from people and things using
    ++/-- syntax, with reason tracking, leaderboards, and admin controls.
    """

    @property
    def name(self) -> str:
        return "plusplus"

    @property
    def description(self) -> str:
        return "Karma/point tracking with ++/-- syntax"

    @property
    def table_prefix(self) -> str:
        return "plugin_plusplus_"

    async def register(
        self,
        app: AsyncApp,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        """Register message listeners and slash commands on the Bolt app."""
        handlers = PlusPlusHandlers(session_factory, settings)

        @app.event("message")
        async def on_message(event, say, client):
            await handlers.handle_message(event, say, client)

        @app.command("/plusplus")
        async def on_plusplus_command(ack, body, respond, client):
            await handlers.handle_slash_command(ack, body, respond, client)

        logger.info("PlusPlus plugin registered: message listener + /plusplus command")

    def register_cli(self, parent_app: Any) -> None:
        """Register ``kennabot plusplus`` CLI subcommands."""
        from kennabot.plugins.plusplus.cli import create_plusplus_cli

        plusplus_app = create_plusplus_cli()
        parent_app.add_typer(plusplus_app, name="plusplus")
