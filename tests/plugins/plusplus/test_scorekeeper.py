"""Tests for the PlusPlus scorekeeper module."""

from __future__ import annotations

import pytest

from kennabot.plugins.plusplus import scorekeeper


class TestAdd:
    """Tests for scorekeeper.add()."""

    @pytest.mark.asyncio
    async def test_add_point(self, db_session_factory):
        result = await scorekeeper.add(
            db_session_factory,
            name="alice",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )
        assert result.success is True
        assert result.total_score == 1
        assert result.delta == 1
        assert result.name == "alice"

    @pytest.mark.asyncio
    async def test_add_multiple_points(self, db_session_factory):
        await scorekeeper.add(
            db_session_factory,
            name="bob",
            from_user_id="U_VOTER1",
            channel_id="C_GENERAL",
            cooldown_seconds=0,  # Disable cooldown for testing
        )
        result = await scorekeeper.add(
            db_session_factory,
            name="bob",
            from_user_id="U_VOTER2",
            channel_id="C_GENERAL",
            cooldown_seconds=0,
        )
        assert result.success is True
        assert result.total_score == 2

    @pytest.mark.asyncio
    async def test_add_with_reason(self, db_session_factory):
        result = await scorekeeper.add(
            db_session_factory,
            name="charlie",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
            reason="fixing bugs",
        )
        assert result.success is True
        assert result.reason == "fixing bugs"
        assert result.reason_score == 1

    @pytest.mark.asyncio
    async def test_add_accumulates_reason(self, db_session_factory):
        await scorekeeper.add(
            db_session_factory,
            name="dave",
            from_user_id="U_VOTER1",
            channel_id="C_GENERAL",
            reason="being cool",
            cooldown_seconds=0,
        )
        result = await scorekeeper.add(
            db_session_factory,
            name="dave",
            from_user_id="U_VOTER2",
            channel_id="C_GENERAL",
            reason="being cool",
            cooldown_seconds=0,
        )
        assert result.reason_score == 2

    @pytest.mark.asyncio
    async def test_self_vote_prevented(self, db_session_factory):
        result = await scorekeeper.add(
            db_session_factory,
            name="selfie",
            from_user_id="U_SELF",
            channel_id="C_GENERAL",
            is_user=True,
            slack_user_id="U_SELF",
        )
        assert result.success is False
        assert result.error == "self_vote"

    @pytest.mark.asyncio
    async def test_spam_prevented(self, db_session_factory):
        # First vote succeeds
        result1 = await scorekeeper.add(
            db_session_factory,
            name="spam_target",
            from_user_id="U_SPAMMER",
            channel_id="C_GENERAL",
            cooldown_seconds=60,  # Long cooldown for test
        )
        assert result1.success is True

        # Immediate second vote from same user to same target is spam
        result2 = await scorekeeper.add(
            db_session_factory,
            name="spam_target",
            from_user_id="U_SPAMMER",
            channel_id="C_GENERAL",
            cooldown_seconds=60,
        )
        assert result2.success is False
        assert result2.error == "spam"

    @pytest.mark.asyncio
    async def test_empty_name_rejected(self, db_session_factory):
        result = await scorekeeper.add(
            db_session_factory,
            name="",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )
        assert result.success is False
        assert result.error == "empty_name"

    @pytest.mark.asyncio
    async def test_is_user_flag(self, db_session_factory):
        result = await scorekeeper.add(
            db_session_factory,
            name="user_test",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
            is_user=True,
            slack_user_id="U_TARGET",
        )
        assert result.success is True


class TestSubtract:
    """Tests for scorekeeper.subtract()."""

    @pytest.mark.asyncio
    async def test_subtract_point(self, db_session_factory):
        result = await scorekeeper.subtract(
            db_session_factory,
            name="negative_nancy",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )
        assert result.success is True
        assert result.total_score == -1
        assert result.delta == -1

    @pytest.mark.asyncio
    async def test_subtract_with_reason(self, db_session_factory):
        result = await scorekeeper.subtract(
            db_session_factory,
            name="bad_thing",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
            reason="terrible",
        )
        assert result.success is True
        assert result.reason == "terrible"
        assert result.reason_score == -1


class TestGetScore:
    """Tests for scorekeeper.get_score()."""

    @pytest.mark.asyncio
    async def test_get_existing_score(self, db_session_factory):
        await scorekeeper.add(
            db_session_factory,
            name="lookup_test",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
            reason="test reason",
        )

        result = await scorekeeper.get_score(db_session_factory, "lookup_test")
        assert result is not None
        total, reasons = result
        assert total == 1
        assert len(reasons) == 1
        assert reasons[0] == ("test reason", 1)

    @pytest.mark.asyncio
    async def test_get_nonexistent_score(self, db_session_factory):
        result = await scorekeeper.get_score(db_session_factory, "nobody")
        assert result is None


class TestTopBottom:
    """Tests for scorekeeper.top() and scorekeeper.bottom()."""

    @pytest.mark.asyncio
    async def test_top(self, db_session_factory):
        # Create some scores
        for i, name in enumerate(["first", "second", "third"]):
            for j in range(3 - i):
                await scorekeeper.add(
                    db_session_factory,
                    name=name,
                    from_user_id=f"U_VOTER{j}",
                    channel_id="C_GENERAL",
                    cooldown_seconds=0,
                )

        entries = await scorekeeper.top(db_session_factory, 3)
        assert len(entries) >= 1
        # First entry should have the highest score
        assert entries[0][1] >= entries[-1][1]

    @pytest.mark.asyncio
    async def test_bottom(self, db_session_factory):
        await scorekeeper.subtract(
            db_session_factory,
            name="worst_thing",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
            cooldown_seconds=0,
        )
        entries = await scorekeeper.bottom(db_session_factory, 10)
        assert len(entries) >= 1


class TestErase:
    """Tests for scorekeeper.erase()."""

    @pytest.mark.asyncio
    async def test_erase_entity(self, db_session_factory):
        await scorekeeper.add(
            db_session_factory,
            name="to_erase",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
        )

        erased = await scorekeeper.erase(db_session_factory, "to_erase")
        assert erased is True

        # Should be gone now
        result = await scorekeeper.get_score(db_session_factory, "to_erase")
        assert result is None

    @pytest.mark.asyncio
    async def test_erase_reason(self, db_session_factory):
        await scorekeeper.add(
            db_session_factory,
            name="partial_erase",
            from_user_id="U_VOTER",
            channel_id="C_GENERAL",
            reason="good reason",
        )

        erased = await scorekeeper.erase(db_session_factory, "partial_erase", reason="good reason")
        assert erased is True

        # Score should still exist, but reason should be gone
        result = await scorekeeper.get_score(db_session_factory, "partial_erase")
        assert result is not None
        total, reasons = result
        assert total == 1  # Total score unchanged
        assert len(reasons) == 0  # Reason removed

    @pytest.mark.asyncio
    async def test_erase_nonexistent(self, db_session_factory):
        erased = await scorekeeper.erase(db_session_factory, "does_not_exist")
        assert erased is False


class TestMRU:
    """Tests for MRU (Most Recently Used) tracking."""

    def test_set_and_get_last(self):
        scorekeeper.set_last("C_TEST", "pizza", "being delicious")
        result = scorekeeper.get_last("C_TEST")
        assert result is not None
        assert result == ("pizza", "being delicious")

    def test_get_last_unknown_channel(self):
        result = scorekeeper.get_last("C_UNKNOWN_CHANNEL")
        assert result is None

    def test_mru_updated_on_score_change(self, db_session_factory):
        # MRU is updated inside the score change functions via set_last()
        # This is tested implicitly through the handler tests
        scorekeeper.set_last("C_MRU", "latest", None)
        result = scorekeeper.get_last("C_MRU")
        assert result == ("latest", None)

    def test_thread_mru_isolation(self):
        """Thread MRU should be separate from channel MRU."""
        scorekeeper.set_last("C_THREAD_TEST", "channel_thing", "channel reason")
        scorekeeper.set_last("C_THREAD_TEST", "thread_thing", "thread reason", "1234567890.123456")

        # Channel MRU should be "channel_thing"
        channel_result = scorekeeper.get_last("C_THREAD_TEST")
        assert channel_result is not None
        assert channel_result == ("channel_thing", "channel reason")

        # Thread MRU should be "thread_thing"
        thread_result = scorekeeper.get_last("C_THREAD_TEST", "1234567890.123456")
        assert thread_result is not None
        assert thread_result == ("thread_thing", "thread reason")

    def test_thread_mru_does_not_affect_channel(self):
        """Setting thread MRU should not change channel MRU."""
        scorekeeper.set_last("C_ISOL", "original", "original reason")
        scorekeeper.set_last("C_ISOL", "thread_only", "thread reason", "9999999999.999999")

        result = scorekeeper.get_last("C_ISOL")
        assert result is not None
        assert result == ("original", "original reason")

    def test_different_threads_isolated(self):
        """Different threads in the same channel should have separate MRU."""
        scorekeeper.set_last("C_MULTI", "thread_a_thing", None, "1111111111.111111")
        scorekeeper.set_last("C_MULTI", "thread_b_thing", None, "2222222222.222222")

        result_a = scorekeeper.get_last("C_MULTI", "1111111111.111111")
        assert result_a is not None
        assert result_a == ("thread_a_thing", None)

        result_b = scorekeeper.get_last("C_MULTI", "2222222222.222222")
        assert result_b is not None
        assert result_b == ("thread_b_thing", None)

    def test_thread_mru_fallback_not_automatic(self):
        """get_last with thread_ts should NOT fall back to channel MRU."""
        scorekeeper.set_last("C_FALLBACK", "channel_item", None)

        # Thread MRU was never set, should return None
        result = scorekeeper.get_last("C_FALLBACK", "8888888888.888888")
        assert result is None


class TestThreadAwareScoring:
    """Tests for thread_ts parameter in add/subtract."""

    @pytest.mark.asyncio
    async def test_add_with_thread_ts_sets_thread_mru(self, db_session_factory):
        """Score change in a thread should set thread MRU, not channel MRU."""
        # Clear any existing MRU state
        scorekeeper._mru_cache.clear()

        await scorekeeper.add(
            db_session_factory,
            name="thread_pizza",
            from_user_id="U_VOTER",
            channel_id="C_THREAD_SCORE",
            reason="in thread",
            thread_ts="1234567890.000001",
        )

        # Thread MRU should be set
        thread_result = scorekeeper.get_last("C_THREAD_SCORE", "1234567890.000001")
        assert thread_result is not None
        assert thread_result[0] == "thread_pizza"

        # Channel MRU should NOT be set
        channel_result = scorekeeper.get_last("C_THREAD_SCORE")
        assert channel_result is None

    @pytest.mark.asyncio
    async def test_add_without_thread_ts_sets_channel_mru(self, db_session_factory):
        """Score change in main channel should set channel MRU."""
        scorekeeper._mru_cache.clear()

        await scorekeeper.add(
            db_session_factory,
            name="channel_testing",
            from_user_id="U_VOTER",
            channel_id="C_CHAN_SCORE",
            reason="in channel",
        )

        channel_result = scorekeeper.get_last("C_CHAN_SCORE")
        assert channel_result is not None
        assert channel_result[0] == "channel_testing"

    @pytest.mark.asyncio
    async def test_subtract_with_thread_ts_sets_thread_mru(self, db_session_factory):
        """Subtract in a thread should set thread MRU, not channel MRU."""
        scorekeeper._mru_cache.clear()

        await scorekeeper.subtract(
            db_session_factory,
            name="thread_bugs",
            from_user_id="U_VOTER",
            channel_id="C_SUB_THREAD",
            reason="in thread",
            thread_ts="5555555555.000001",
        )

        thread_result = scorekeeper.get_last("C_SUB_THREAD", "5555555555.000001")
        assert thread_result is not None
        assert thread_result[0] == "thread_bugs"

        channel_result = scorekeeper.get_last("C_SUB_THREAD")
        assert channel_result is None

    @pytest.mark.asyncio
    async def test_channel_and_thread_mru_independent(self, db_session_factory):
        """Channel and thread votes should maintain independent MRU."""
        scorekeeper._mru_cache.clear()

        # Vote in channel
        await scorekeeper.add(
            db_session_factory,
            name="channel_item",
            from_user_id="U_VOTER1",
            channel_id="C_INDEP",
            cooldown_seconds=0,
        )

        # Vote in thread
        await scorekeeper.add(
            db_session_factory,
            name="thread_item",
            from_user_id="U_VOTER2",
            channel_id="C_INDEP",
            thread_ts="7777777777.000001",
            cooldown_seconds=0,
        )

        # Channel MRU should still be channel_item
        channel_result = scorekeeper.get_last("C_INDEP")
        assert channel_result is not None
        assert channel_result[0] == "channel_item"

        # Thread MRU should be thread_item
        thread_result = scorekeeper.get_last("C_INDEP", "7777777777.000001")
        assert thread_result is not None
        assert thread_result[0] == "thread_item"
