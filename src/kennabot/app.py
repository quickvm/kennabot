"""Slack Bolt AsyncApp and FastAPI application setup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from kennabot import __version__

if TYPE_CHECKING:
    from kennabot.config import Settings

logger = logging.getLogger(__name__)


def create_bolt_app(settings: Settings) -> AsyncApp:
    """Create and configure the Slack Bolt async application."""
    bolt_app = AsyncApp(
        token=settings.slack_bot_token,
        request_verification_enabled=False,
    )
    logger.info("Slack Bolt AsyncApp created")
    return bolt_app


def create_fastapi_app(settings: Settings) -> FastAPI:
    """Create the FastAPI application with health and info endpoints."""
    api = FastAPI(
        title="KennaBot",
        version=__version__,
        description="A modern Slack bot",
    )

    @api.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @api.get("/")
    async def root() -> dict[str, str]:
        return {"name": "KennaBot", "version": __version__}

    return api


async def start_socket_mode(bolt_app: AsyncApp, settings: Settings) -> AsyncSocketModeHandler:
    """Start the Socket Mode handler for the Bolt app."""
    handler = AsyncSocketModeHandler(
        app=bolt_app,
        app_token=settings.slack_app_token,
    )
    logger.info("Starting Socket Mode connection...")
    return handler
