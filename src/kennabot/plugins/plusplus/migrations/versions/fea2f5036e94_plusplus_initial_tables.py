"""plusplus initial tables

Revision ID: fea2f5036e94
Revises:
Create Date: 2026-02-17 20:50:43.184751

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fea2f5036e94"
down_revision: str | tuple[str, ...] | None = None
branch_labels: str | Sequence[str] | None = ("plusplus",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plugin_plusplus_score_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.String(), nullable=False),
        sa.Column("to_name", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("plugin_plusplus_score_log", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_plugin_plusplus_score_log_from_user_id"),
            ["from_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_plugin_plusplus_score_log_to_name"),
            ["to_name"],
            unique=False,
        )

    op.create_table(
        "plugin_plusplus_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("is_user", sa.Boolean(), nullable=False),
        sa.Column("slack_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("plugin_plusplus_scores", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_plugin_plusplus_scores_name"), ["name"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_plugin_plusplus_scores_slack_user_id"),
            ["slack_user_id"],
            unique=False,
        )

    op.create_table(
        "plugin_plusplus_score_reasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["score_id"],
            ["plugin_plusplus_scores.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("score_id", "reason", name="uq_plugin_plusplus_score_reason"),
    )
    with op.batch_alter_table("plugin_plusplus_score_reasons", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_plugin_plusplus_score_reasons_score_id"),
            ["score_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("plugin_plusplus_score_reasons", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_plugin_plusplus_score_reasons_score_id"))
    op.drop_table("plugin_plusplus_score_reasons")

    with op.batch_alter_table("plugin_plusplus_scores", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_plugin_plusplus_scores_slack_user_id"))
        batch_op.drop_index(batch_op.f("ix_plugin_plusplus_scores_name"))
    op.drop_table("plugin_plusplus_scores")

    with op.batch_alter_table("plugin_plusplus_score_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_plugin_plusplus_score_log_to_name"))
        batch_op.drop_index(batch_op.f("ix_plugin_plusplus_score_log_from_user_id"))
    op.drop_table("plugin_plusplus_score_log")
