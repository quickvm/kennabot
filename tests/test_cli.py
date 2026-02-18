"""Tests for the KennaBot CLI."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _cli_env(tmp_path, monkeypatch):
    """Set up environment variables for CLI tests.

    Every test gets a fresh temp database and dummy Slack tokens.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("KENNABOT_SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("KENNABOT_SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("KENNABOT_DB_PATH", db_path)


class TestRootCLI:
    """Tests for root-level CLI commands."""

    def test_version(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "kennabot 0.1.0" in result.output

    def test_help(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "serve" in result.output
        assert "db" in result.output
        assert "config" in result.output
        assert "plugin" in result.output
        assert "plusplus" in result.output

    def test_serve_help(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--log-level" in result.output


class TestDBCommands:
    """Tests for ``kennabot db`` commands."""

    def test_db_init(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["db", "init"])
        assert result.exit_code == 0
        assert "Database initialized" in result.output

    def test_db_migrate(self):
        from kennabot.cli import app

        # Init first to create the DB, then migrate should be a no-op
        runner.invoke(app, ["db", "init"])
        result = runner.invoke(app, ["db", "migrate"])
        assert result.exit_code == 0
        assert "Migrations applied" in result.output


class TestConfigCommands:
    """Tests for ``kennabot config`` commands."""

    def test_config_show(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "SLACK_BOT_TOKEN:" in result.output
        assert "xoxb-tes" in result.output
        # Token should be redacted (not show full value)
        assert "xoxb-test-token" not in result.output
        assert "DB_PATH:" in result.output
        assert "COOLDOWN_SECONDS:" in result.output

    def test_config_validate_token_format(self):
        from kennabot.cli import app

        # Tokens have valid prefixes, but API call will fail (dummy tokens)
        result = runner.invoke(app, ["config", "validate"])
        # Token format checks should pass
        assert "SLACK_BOT_TOKEN has valid prefix" in result.output
        assert "SLACK_APP_TOKEN has valid prefix" in result.output
        # Slack API call will fail with dummy tokens
        assert "Slack API:" in result.output


class TestPluginCommands:
    """Tests for ``kennabot plugin`` commands."""

    def test_plugin_list(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["plugin", "list"])
        assert result.exit_code == 0
        assert "plusplus" in result.output
        assert "[CLI]" in result.output


class TestPlusPlusCommands:
    """Tests for ``kennabot plusplus`` commands (registered by plugin)."""

    def test_plusplus_help(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["plusplus", "--help"])
        assert result.exit_code == 0
        assert "get" in result.output
        assert "top" in result.output
        assert "bottom" in result.output
        assert "set" in result.output
        assert "erase" in result.output
        assert "import-hubot" in result.output
        assert "stats" in result.output
        assert "export" in result.output

    def test_plusplus_get_not_found(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        result = runner.invoke(app, ["plusplus", "get", "nobody"])
        assert result.exit_code == 1
        assert "No score found" in result.output

    def test_plusplus_set_requires_force(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        result = runner.invoke(app, ["plusplus", "set", "alice", "50"])
        assert result.exit_code == 1
        assert "--force" in result.output

    def test_plusplus_set_with_force(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        result = runner.invoke(app, ["plusplus", "set", "alice", "50", "--force"])
        assert result.exit_code == 0
        assert "alice: 0 -> 50" in result.output

    def test_plusplus_get_after_set(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        runner.invoke(app, ["plusplus", "set", "bob", "25", "--force"])
        result = runner.invoke(app, ["plusplus", "get", "bob"])
        assert result.exit_code == 0
        assert "bob: 25 points" in result.output

    def test_plusplus_top(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        runner.invoke(app, ["plusplus", "set", "alice", "50", "--force"])
        runner.invoke(app, ["plusplus", "set", "bob", "30", "--force"])
        result = runner.invoke(app, ["plusplus", "top", "--limit", "5"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bob" in result.output

    def test_plusplus_bottom(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        # Add two entries — bottom should show the lowest first
        runner.invoke(app, ["plusplus", "set", "high-scorer", "100", "--force"])
        runner.invoke(app, ["plusplus", "set", "low-scorer", "1", "--force"])

        result = runner.invoke(app, ["plusplus", "bottom", "--limit", "5"])
        assert result.exit_code == 0
        assert "low-scorer" in result.output

    def test_plusplus_erase(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        runner.invoke(app, ["plusplus", "set", "to-erase", "5", "--force"])
        result = runner.invoke(app, ["plusplus", "erase", "to-erase"])
        assert result.exit_code == 0
        assert "Erased all scores" in result.output

        # Should be gone now
        result = runner.invoke(app, ["plusplus", "get", "to-erase"])
        assert result.exit_code == 1
        assert "No score found" in result.output

    def test_plusplus_erase_not_found(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        result = runner.invoke(app, ["plusplus", "erase", "nonexistent"])
        assert result.exit_code == 1
        assert "No scores found" in result.output

    def test_plusplus_import_hubot_from_file(self, tmp_path):
        from kennabot.cli import app

        # Create a test hubot brain dump
        brain_data = {
            "plusPlus": {
                "scores": {
                    "alice": 42,
                    "bob": 10,
                    "pizza": 100,
                },
                "reasons": {
                    "alice": {
                        "being awesome": 15,
                        "fixing bugs": 8,
                    },
                    "pizza": {
                        "being delicious": 50,
                    },
                },
            }
        }
        dump_file = tmp_path / "brain_dump.json"
        with dump_file.open("w") as f:
            json.dump(brain_data, f)

        result = runner.invoke(
            app,
            ["plusplus", "import-hubot", "--from-file", str(dump_file)],
        )
        assert result.exit_code == 0
        assert "3 scores" in result.output
        assert "3 reasons" in result.output

        # Verify imported data
        result = runner.invoke(app, ["plusplus", "get", "alice"])
        assert result.exit_code == 0
        assert "42 points" in result.output
        assert "being awesome" in result.output

    def test_plusplus_import_hubot_dry_run(self, tmp_path):
        from kennabot.cli import app

        brain_data = {
            "plusPlus": {
                "scores": {"alice": 42},
                "reasons": {},
            }
        }
        dump_file = tmp_path / "brain_dump.json"
        with dump_file.open("w") as f:
            json.dump(brain_data, f)

        runner.invoke(app, ["db", "init"])
        result = runner.invoke(
            app,
            ["plusplus", "import-hubot", "--from-file", str(dump_file), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "alice" in result.output

    def test_plusplus_stats(self):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        result = runner.invoke(app, ["plusplus", "stats"])
        assert result.exit_code == 0
        assert "Scores:" in result.output
        assert "Reasons:" in result.output
        assert "Log entries:" in result.output

    def test_plusplus_export(self, tmp_path):
        from kennabot.cli import app

        runner.invoke(app, ["db", "init"])
        runner.invoke(app, ["plusplus", "set", "alice", "42", "--force"])

        output_file = str(tmp_path / "export.json")
        result = runner.invoke(app, ["plusplus", "export", "--output", output_file])
        assert result.exit_code == 0
        assert "Exported" in result.output

        with open(output_file) as f:
            data = json.load(f)
        assert "scores" in data
        assert "alice" in data["scores"]
        assert data["scores"]["alice"] == 42

    def test_plusplus_import_hubot_no_source(self):
        from kennabot.cli import app

        result = runner.invoke(app, ["plusplus", "import-hubot"])
        assert result.exit_code == 1
        assert "--redis-url" in result.output or "--from-file" in result.output
