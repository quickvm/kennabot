"""Tests for the PlusPlus handlers module."""

from __future__ import annotations

import pytest

from kennabot.plugins.plusplus import scorekeeper
from kennabot.plugins.plusplus.handlers import PlusPlusHandlers


@pytest.fixture
def handlers(db_session_factory, settings):
    """Create a PlusPlusHandlers instance with test dependencies."""
    return PlusPlusHandlers(db_session_factory, settings)


class TestHandleMessage:
    """Tests for PlusPlusHandlers.handle_message()."""

    @pytest.mark.asyncio
    async def test_user_mention_increment(
        self, handlers, mock_say, mock_client, db_session_factory
    ):
        message = {
            "text": "<@U_TARGET>++",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "<@U_TARGET>" in call_args
        assert "+1" in call_args

    @pytest.mark.asyncio
    async def test_plain_name_increment(self, handlers, mock_say, mock_client):
        message = {
            "text": "pizza++",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "pizza" in call_args
        assert "+1" in call_args

    @pytest.mark.asyncio
    async def test_decrement(self, handlers, mock_say, mock_client):
        message = {
            "text": "meetings--",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "meetings" in call_args
        assert "-1" in call_args

    @pytest.mark.asyncio
    async def test_with_reason(self, handlers, mock_say, mock_client):
        message = {
            "text": "python++ for being awesome",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "python" in call_args
        assert "being awesome" in call_args

    @pytest.mark.asyncio
    async def test_self_vote_message(self, handlers, mock_say, mock_client):
        message = {
            "text": "<@U_SELF>++",
            "user": "U_SELF",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "can't give yourself" in call_args

    @pytest.mark.asyncio
    async def test_ignores_normal_messages(self, handlers, mock_say, mock_client):
        message = {
            "text": "just a normal message",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self, handlers, mock_say, mock_client):
        message = {
            "text": "pizza++",
            "user": "U_BOT",
            "channel": "C_GENERAL",
            "subtype": "bot_message",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_not_called()

    @pytest.mark.asyncio
    async def test_emdash_decrement(self, handlers, mock_say, mock_client):
        message = {
            "text": "bugs\u2014",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "bugs" in call_args
        assert "-1" in call_args


class TestHandleMessageThreads:
    """Tests for thread-aware message handling."""

    @pytest.mark.asyncio
    async def test_thread_reply_responds_in_thread(self, handlers, mock_say, mock_client):
        """Messages in a thread should get replies in the thread."""
        message = {
            "text": "pizza++",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
            "thread_ts": "1234567890.000001",
            "ts": "1234567890.000099",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        # Should pass thread_ts kwarg to say()
        assert mock_say.call_args.kwargs.get("thread_ts") == "1234567890.000001"

    @pytest.mark.asyncio
    async def test_channel_message_no_thread_ts(self, handlers, mock_say, mock_client):
        """Messages in the main channel should not pass thread_ts."""
        message = {
            "text": "pizza++",
            "user": "U_VOTER",
            "channel": "C_GENERAL",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        # Should NOT pass thread_ts kwarg
        assert "thread_ts" not in (mock_say.call_args.kwargs or {})

    @pytest.mark.asyncio
    async def test_bare_increment_in_thread_uses_thread_mru(self, handlers, mock_say, mock_client):
        """Bare ++ in a thread should use the thread's MRU, not the channel's."""
        scorekeeper._mru_cache.clear()

        # First, set a named vote in the thread
        message1 = {
            "text": "pizza++ for thread test",
            "user": "U_VOTER",
            "channel": "C_THREAD_HANDLER",
            "thread_ts": "1111111111.000001",
            "ts": "1111111111.000002",
        }
        await handlers.handle_message(message1, mock_say, mock_client)
        mock_say.reset_mock()

        # Set a different channel MRU
        scorekeeper.set_last("C_THREAD_HANDLER", "channel_thing", "channel reason")

        # Bare ++ in the same thread should give to pizza
        message2 = {
            "text": "++",
            "user": "U_VOTER2",
            "channel": "C_THREAD_HANDLER",
            "thread_ts": "1111111111.000001",
            "ts": "1111111111.000003",
        }
        await handlers.handle_message(message2, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "pizza" in call_args

    @pytest.mark.asyncio
    async def test_bare_increment_in_channel_uses_channel_mru(
        self, handlers, mock_say, mock_client
    ):
        """Bare ++ in the channel should use channel MRU, not thread MRU."""
        scorekeeper._mru_cache.clear()

        # Set channel MRU
        scorekeeper.set_last("C_CHAN_HANDLER", "testing", "channel reason")
        # Set a thread MRU
        scorekeeper.set_last("C_CHAN_HANDLER", "thread_pizza", "thread reason", "2222222222.000001")

        # Bare ++ in channel should give to testing, not thread_pizza
        message = {
            "text": "++",
            "user": "U_VOTER",
            "channel": "C_CHAN_HANDLER",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "testing" in call_args

    @pytest.mark.asyncio
    async def test_bare_increment_in_thread_falls_back_to_channel(
        self, handlers, mock_say, mock_client
    ):
        """Bare ++ in thread with no thread MRU should fall back to channel MRU."""
        scorekeeper._mru_cache.clear()

        # Only set channel MRU
        scorekeeper.set_last("C_FB_HANDLER", "fallback_thing", "fb reason")

        # Bare ++ in a thread with no thread MRU
        message = {
            "text": "++",
            "user": "U_VOTER",
            "channel": "C_FB_HANDLER",
            "thread_ts": "3333333333.000001",
            "ts": "3333333333.000002",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_called_once()
        call_args = mock_say.call_args[0][0]
        assert "fallback_thing" in call_args

    @pytest.mark.asyncio
    async def test_bare_increment_no_mru_anywhere(self, handlers, mock_say, mock_client):
        """Bare ++ with no MRU anywhere should be silently ignored."""
        scorekeeper._mru_cache.clear()

        message = {
            "text": "++",
            "user": "U_VOTER",
            "channel": "C_EMPTY_MRU",
        }
        await handlers.handle_message(message, mock_say, mock_client)
        mock_say.assert_not_called()


class TestHandleSlashCommand:
    """Tests for PlusPlusHandlers.handle_slash_command()."""

    @pytest.mark.asyncio
    async def test_help(self, handlers, mock_ack, mock_respond, mock_client):
        body = {"text": "", "user_id": "U_ADMIN"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        mock_respond.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "PlusPlus" in call_args

    @pytest.mark.asyncio
    async def test_help_explicit(self, handlers, mock_ack, mock_respond, mock_client):
        body = {"text": "help", "user_id": "U_ADMIN"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "PlusPlus" in call_args

    @pytest.mark.asyncio
    async def test_top(self, handlers, mock_ack, mock_respond, mock_client, db_session_factory):
        # Add some scores first
        from kennabot.plugins.plusplus import scorekeeper

        await scorekeeper.add(
            db_session_factory,
            name="top_test",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )

        body = {"text": "top 5", "user_id": "U_USER"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "Top" in call_args

    @pytest.mark.asyncio
    async def test_bottom(self, handlers, mock_ack, mock_respond, mock_client):
        body = {"text": "bottom 3", "user_id": "U_USER"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "Bottom" in call_args

    @pytest.mark.asyncio
    async def test_score_lookup(
        self, handlers, mock_ack, mock_respond, mock_client, db_session_factory
    ):
        from kennabot.plugins.plusplus import scorekeeper

        await scorekeeper.add(
            db_session_factory,
            name="lookup_cmd_test",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )

        body = {"text": "lookup_cmd_test", "user_id": "U_USER"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "lookup_cmd_test" in call_args

    @pytest.mark.asyncio
    async def test_score_lookup_not_found(self, handlers, mock_ack, mock_respond, mock_client):
        body = {"text": "unknown_entity", "user_id": "U_USER"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "No score found" in call_args

    @pytest.mark.asyncio
    async def test_erase_without_admin(self, handlers, mock_ack, mock_respond, mock_client):
        # Set admin users to restrict access
        handlers.settings.admin_users = ["U_ADMIN"]

        body = {"text": "erase something", "user_id": "U_REGULAR"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_erase_as_admin(
        self, handlers, mock_ack, mock_respond, mock_client, db_session_factory
    ):
        from kennabot.plugins.plusplus import scorekeeper

        await scorekeeper.add(
            db_session_factory,
            name="to_erase_cmd",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )

        handlers.settings.admin_users = ["U_ADMIN"]
        body = {"text": "erase to_erase_cmd", "user_id": "U_ADMIN"}
        await handlers.handle_slash_command(mock_ack, body, mock_respond, mock_client)
        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "Erased" in call_args
