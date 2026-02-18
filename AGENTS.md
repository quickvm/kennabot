# KennaBot Development Guide

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Copy environment template
cp .env.example .env
# Edit .env with your Slack tokens

# Run the bot
uv run kennabot serve

# Run tests
uv run pytest tests/ -v
```

## Development Commands

```bash
# Linting
uv run ruff check src/ tests/
uv run ruff check src/ tests/ --fix  # Auto-fix

# Type checking
uv run ty check src/ tests/

# Run all checks (lint + typecheck + test)
uv run ruff check src/ tests/ && uv run ty check src/ tests/ && uv run pytest tests/ -v
```

## Container Development

```bash
# Build container
podman build -t kennabot .

# Run container
podman run -d \
  --name kennabot \
  --env-file .env \
  -v kennabot_data:/data \
  -p 8080:8080 \
  kennabot

# Access CLI inside container
podman exec kennabot kennabot plusplus top
podman exec kennabot kennabot db stats
```

## Project Conventions

- **Python 3.12+** with async/await throughout
- **Plugin architecture**: Add plugins to `src/kennabot/plugins/`
- **Database**: SQLite via SQLModel + aiosqlite
- **CLI**: Typer with AsyncTyper for async commands
- **Settings**: pydantic-settings (environment variables with `KENNABOT_` prefix)
- **Linting**: Ruff for linting and formatting
- **Type checking**: ty for static type analysis
- **Tests**: pytest + pytest-asyncio, organized by plugin

## Test Structure

Tests are organized to mirror the plugin architecture:

```
tests/
├── conftest.py                          # Shared fixtures (db_session_factory, settings)
├── test_cli.py                          # CLI integration tests
└── plugins/
    └── plusplus/
        ├── conftest.py                  # Plugin-specific fixtures (handlers, mock_client)
        ├── test_handlers.py             # Slack message/command handler tests
        ├── test_helpers.py              # Helper function tests (patterns, formatting)
        └── test_scorekeeper.py          # Score logic + MRU + thread-awareness tests
```

## Key Files

| File | Purpose |
|------|---------|
| `src/kennabot/app.py` | Slack Bolt AsyncApp + FastAPI setup |
| `src/kennabot/config.py` | Settings via pydantic-settings |
| `src/kennabot/database.py` | SQLModel engine and session management |
| `src/kennabot/plugins/base.py` | BasePlugin abstract class |
| `src/kennabot/plugins/plusplus/` | Karma tracking plugin |
| `src/kennabot/plugins/plusplus/handlers.py` | Thread-aware message handling + slash commands |
| `src/kennabot/plugins/plusplus/scorekeeper.py` | Score logic with thread-scoped MRU tracking |
