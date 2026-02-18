"""Central model registry for KennaBot.

Importing this module registers all SQLModel table metadata so that
``SQLModel.metadata`` is populated before schema operations run.

Each plugin owns its models under ``plugins/<name>/models.py``.  Add a new
plugin's models import here so they are discovered at startup and by Alembic.
"""

# Plugin models — imported for SQLModel.metadata side-effects
from kennabot.plugins.plusplus.models import Score, ScoreLog, ScoreReason  # noqa: F401

__all__ = ["Score", "ScoreLog", "ScoreReason"]
