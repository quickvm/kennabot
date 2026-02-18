"""Fixtures specific to the PlusPlus plugin tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from kennabot.plugins.plusplus.handlers import PlusPlusHandlers


@pytest.fixture
def handlers(db_session_factory, settings):
    """Create a PlusPlusHandlers instance with test dependencies."""
    return PlusPlusHandlers(db_session_factory, settings)


@pytest.fixture
def mock_say() -> AsyncMock:
    """Mock Slack `say` function."""
    return AsyncMock()


@pytest.fixture
def mock_respond() -> AsyncMock:
    """Mock Slack `respond` function."""
    return AsyncMock()


@pytest.fixture
def mock_ack() -> AsyncMock:
    """Mock Slack `ack` function."""
    return AsyncMock()


@pytest.fixture
def mock_client() -> AsyncMock:
    """Mock Slack WebClient with users_info.

    Returns different user data based on the user ID queried.
    """
    client = AsyncMock()

    user_data = {
        "U_TARGET": {"id": "U_TARGET", "name": "alice", "real_name": "Alice Smith"},
        "U_VOTER": {"id": "U_VOTER", "name": "voter", "real_name": "Test Voter"},
        "U_VOTER1": {"id": "U_VOTER1", "name": "voter1", "real_name": "Voter One"},
        "U_VOTER2": {"id": "U_VOTER2", "name": "voter2", "real_name": "Voter Two"},
        "U_SELF": {"id": "U_SELF", "name": "selfish", "real_name": "Selfish User"},
    }

    async def users_info_side_effect(*, user: str):
        if user in user_data:
            return {"user": user_data[user]}
        return {"user": {"id": user, "name": user.lower(), "real_name": user}}

    client.users_info.side_effect = users_info_side_effect
    return client
