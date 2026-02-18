"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_env_file_path() -> Path:
    """Get the path to the .env file."""
    # Look for .env in the project root (where pyproject.toml is)
    project_root = Path(__file__).parent.parent.parent
    return project_root / ".env"


def _load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    import os

    env_path = _get_env_file_path()
    if env_path.exists():
        # Read and set env vars from .env file
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key, value)

    # Map SLACK_* vars to KENNABOT_SLACK_* for pydantic
    mappings = {
        "SLACK_BOT_TOKEN": "KENNABOT_SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN": "KENNABOT_SLACK_APP_TOKEN",
    }
    for standard, prefixed in mappings.items():
        if standard in os.environ and prefixed not in os.environ:
            os.environ[prefixed] = os.environ[standard]


class Settings(BaseSettings):
    """KennaBot configuration.

    Slack tokens use standard SLACK_* env var names (no prefix).
    All other settings use the KENNABOT_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="KENNABOT_",
        env_file=_get_env_file_path(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Slack tokens — override prefix to use standard SLACK_* names
    slack_bot_token: str = Field(
        description="Slack Bot User OAuth Token (xoxb-...)",
        json_schema_extra={"env": "SLACK_BOT_TOKEN"},
    )
    slack_app_token: str = Field(
        description="Slack App-Level Token for Socket Mode (xapp-...)",
        json_schema_extra={"env": "SLACK_APP_TOKEN"},
    )

    # Database
    db_path: str = Field(
        default="./data/kennabot.db",
        description="Path to the SQLite database file",
    )

    # PlusPlus settings
    admin_users: list[str] = Field(
        default_factory=list,
        description="Comma-separated Slack user IDs allowed to erase scores",
    )
    cooldown_seconds: int = Field(
        default=5,
        description="Seconds between votes from the same user to the same target",
    )
    reason_conjunctions: list[str] = Field(
        default_factory=lambda: ["for", "because", "cause", "cuz", "as"],
        description="Words that introduce a reason in 'thing++ <conjunction> <reason>' syntax",
    )
    use_display_name: bool = Field(
        default=False,
        description="Use display name (real name) instead of username for score storage",
    )

    # Plugin control
    enabled_plugins: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit list of plugin names to load (e.g. 'plusplus'). "
            "When empty (the default), all discovered plugins are loaded."
        ),
    )

    # General
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    @property
    def db_url(self) -> str:
        """SQLAlchemy-compatible async SQLite URL."""
        return f"sqlite+aiosqlite:///{self.db_path}"


def get_settings() -> Settings:
    """Load settings from environment."""
    _load_env_file()
    return Settings()  # type: ignore[call-arg]
