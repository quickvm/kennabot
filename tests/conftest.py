"""Shared test fixtures for KennaBot tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

os.environ.pop("FORCE_COLOR", None)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session_factory(tmp_path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create an in-memory SQLite database and return a session factory.

    Each test gets its own fresh database.
    """
    db_path = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Import all plugin models so SQLModel.metadata is populated
    import kennabot.models  # noqa: F401  — registers plugin_plusplus_* tables

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield session_factory

    await engine.dispose()


@pytest.fixture
def settings():
    """Create a test Settings-like object."""

    class TestSettings:
        slack_bot_token = "xoxb-test"
        slack_app_token = "xapp-test"
        db_path = ":memory:"
        db_url = "sqlite+aiosqlite:///:memory:"
        admin_users: list[str] = []
        cooldown_seconds = 5
        reason_conjunctions = ["for", "because", "cause", "cuz", "as"]
        use_display_name = False
        log_level = "DEBUG"
        enabled_plugins: list[str] = []

    return TestSettings()
