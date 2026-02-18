"""SQLModel models for the plusplus scoring system.

All tables are prefixed with ``plugin_plusplus_`` to avoid collisions with
other plugins and future core tables.
"""

from datetime import UTC, datetime
from functools import partial
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


class Score(SQLModel, table=True):
    """An entity (user or thing) that can accumulate points."""

    __tablename__ = "plugin_plusplus_scores"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, description="Normalized lowercase name")
    score: int = Field(default=0, description="Current total score")
    is_user: bool = Field(default=False, description="True if this is a Slack user")
    slack_user_id: str | None = Field(
        default=None, index=True, description="Slack user ID (e.g. U0123ABC)"
    )
    created_at: datetime = Field(default_factory=partial(datetime.now, UTC))
    updated_at: datetime = Field(default_factory=partial(datetime.now, UTC))

    reasons: list["ScoreReason"] = Relationship(
        back_populates="score_entry",
        cascade_delete=True,
    )


class ScoreReason(SQLModel, table=True):
    """Per-reason point breakdown for a scored entity."""

    __tablename__ = "plugin_plusplus_score_reasons"
    __table_args__ = (
        UniqueConstraint("score_id", "reason", name="uq_plugin_plusplus_score_reason"),
    )

    id: int | None = Field(default=None, primary_key=True)
    score_id: int = Field(foreign_key="plugin_plusplus_scores.id", index=True)
    reason: str = Field(description="The reason text")
    points: int = Field(default=0, description="Net points for this reason")

    score_entry: Optional["Score"] = Relationship(back_populates="reasons")


class ScoreLog(SQLModel, table=True):
    """Audit log of every point change. Also used for spam prevention."""

    __tablename__ = "plugin_plusplus_score_log"

    id: int | None = Field(default=None, primary_key=True)
    from_user_id: str = Field(index=True, description="Slack user ID of the voter")
    to_name: str = Field(index=True, description="Normalized name of the target")
    direction: str = Field(description="'++' or '--'")
    reason: str | None = Field(default=None, description="Optional reason text")
    channel_id: str = Field(description="Slack channel ID where the vote occurred")
    created_at: datetime = Field(default_factory=partial(datetime.now, UTC))
