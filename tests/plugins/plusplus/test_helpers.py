"""Tests for the PlusPlus helpers module."""

from __future__ import annotations

import pytest

from kennabot.plugins.plusplus.helpers import (
    build_pattern,
    format_leaderboard,
    format_score_detail,
    format_score_message,
    normalize_name,
    normalize_reason,
)


class TestNormalizeName:
    """Tests for normalize_name()."""

    def test_basic_name(self):
        assert normalize_name("Alice") == "alice"

    def test_strip_at_prefix(self):
        assert normalize_name("@alice") == "alice"

    def test_strip_trailing_punctuation(self):
        assert normalize_name("alice,") == "alice"
        assert normalize_name("alice:") == "alice"
        assert normalize_name("alice;") == "alice"
        assert normalize_name("alice.") == "alice"

    def test_strip_whitespace(self):
        assert normalize_name("  alice  ") == "alice"

    def test_strip_quotes(self):
        assert normalize_name('"multi word thing"') == "multi word thing"
        assert normalize_name("'multi word thing'") == "multi word thing"

    def test_empty_name(self):
        assert normalize_name("") == ""

    def test_name_with_hyphens_and_dots(self):
        assert normalize_name("first-last") == "first-last"
        assert normalize_name("user.name") == "user.name"

    def test_lowercase(self):
        assert normalize_name("PYTHON") == "python"
        assert normalize_name("FastAPI") == "fastapi"


class TestNormalizeReason:
    """Tests for normalize_reason()."""

    def test_basic_reason(self):
        assert normalize_reason("Being Awesome") == "being awesome"

    def test_strip_whitespace(self):
        assert normalize_reason("  fixing bugs  ") == "fixing bugs"


class TestBuildPattern:
    """Tests for build_pattern() regex matching."""

    @pytest.fixture
    def pattern(self):
        return build_pattern()

    def test_user_mention_increment(self, pattern):
        m = pattern.match("<@U12345>++")
        assert m is not None
        assert m.group(1) == "U12345"
        assert m.group(3) == "++"

    def test_user_mention_decrement(self, pattern):
        m = pattern.match("<@U12345>--")
        assert m is not None
        assert m.group(1) == "U12345"
        assert m.group(3) == "--"

    def test_user_mention_emdash(self, pattern):
        m = pattern.match("<@U12345>\u2014")
        assert m is not None
        assert m.group(1) == "U12345"
        assert m.group(3) == "\u2014"

    def test_plain_name_increment(self, pattern):
        m = pattern.match("pizza++")
        assert m is not None
        assert m.group(2) == "pizza"
        assert m.group(3) == "++"

    def test_plain_name_decrement(self, pattern):
        m = pattern.match("meetings--")
        assert m is not None
        assert m.group(2) == "meetings"
        assert m.group(3) == "--"

    def test_with_reason_for(self, pattern):
        m = pattern.match("<@U12345>++ for being awesome")
        assert m is not None
        assert m.group(1) == "U12345"
        assert m.group(3) == "++"
        assert m.group(4) == "being awesome"

    def test_with_reason_because(self, pattern):
        m = pattern.match("pizza++ because it is delicious")
        assert m is not None
        assert m.group(2) == "pizza"
        assert m.group(4) == "it is delicious"

    def test_with_reason_cuz(self, pattern):
        m = pattern.match("python++ cuz it rocks")
        assert m is not None
        assert m.group(4) == "it rocks"

    def test_bare_increment(self, pattern):
        m = pattern.match("++")
        assert m is not None
        assert m.group(1) is None
        assert m.group(2) is None
        assert m.group(3) == "++"

    def test_bare_decrement(self, pattern):
        m = pattern.match("--")
        assert m is not None
        assert m.group(3) == "--"

    def test_name_with_space_before_operator(self, pattern):
        m = pattern.match("<@U12345> ++")
        assert m is not None
        assert m.group(1) == "U12345"
        assert m.group(3) == "++"

    def test_no_match_regular_message(self, pattern):
        assert pattern.match("hello world") is None
        assert pattern.match("this is a normal message") is None

    def test_custom_conjunctions(self):
        pat = build_pattern(["pour", "parce que"])
        m = pat.match("python++ pour being great")
        assert m is not None
        assert m.group(4) == "being great"


class TestFormatScoreMessage:
    """Tests for format_score_message()."""

    def test_basic_increment(self):
        msg = format_score_message(
            name="alice",
            display_name="<@U12345>",
            total_score=10,
            delta=1,
        )
        assert "<@U12345> has 10 points (+1)." in msg

    def test_basic_decrement(self):
        msg = format_score_message(
            name="bob",
            display_name="bob",
            total_score=-3,
            delta=-1,
        )
        assert "bob has -3 points (-1)." in msg

    def test_with_reason(self):
        msg = format_score_message(
            name="alice",
            display_name="alice",
            total_score=5,
            delta=1,
            reason="fixing bugs",
            reason_score=3,
        )
        assert "alice has 5 points (+1)." in msg
        assert "3 points are for fixing bugs." in msg

    def test_singular_point(self):
        msg = format_score_message(
            name="new_user",
            display_name="new_user",
            total_score=1,
            delta=1,
        )
        assert "1 point (+1)." in msg

    def test_singular_reason_point(self):
        msg = format_score_message(
            name="user",
            display_name="user",
            total_score=5,
            delta=1,
            reason="test",
            reason_score=1,
        )
        assert "1 point is for test." in msg


class TestFormatLeaderboard:
    """Tests for format_leaderboard()."""

    def test_basic_leaderboard(self):
        entries = [("alice", 42), ("bob", 10), ("pizza", 5)]
        msg = format_leaderboard(entries, title="Top 3")
        assert "*Top 3*" in msg
        assert "1. alice" in msg
        assert "2. bob" in msg
        assert "3. pizza" in msg

    def test_empty_leaderboard(self):
        msg = format_leaderboard([], title="Top scores")
        assert "No scores yet!" in msg


class TestFormatScoreDetail:
    """Tests for format_score_detail()."""

    def test_with_reasons(self):
        msg = format_score_detail(
            display_name="alice",
            total_score=42,
            reasons=[("fixing bugs", 15), ("code reviews", 8)],
        )
        assert "*alice* has 42 points." in msg
        assert "fixing bugs: 15" in msg
        assert "code reviews: 8" in msg

    def test_without_reasons(self):
        msg = format_score_detail(
            display_name="pizza",
            total_score=10,
            reasons=[],
        )
        assert "*pizza* has 10 points." in msg
        assert "Top reasons" not in msg
