# KennaBot

A modern Slack bot built with Python, replacing [Hubot](https://github.com/hubotio/hubot) and [hubot-plusplus](https://github.com/ajacksified/hubot-plusplus). Uses Socket Mode for Slack connectivity, SQLite for persistence, Alembic for schema migrations, and a plugin architecture for extensibility.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Package Manager | [uv](https://docs.astral.sh/uv/) |
| Slack Framework | [slack-bolt](https://slack.dev/bolt-python/) (AsyncApp) + [slack-sdk](https://slack.dev/python-slack-sdk/) |
| Transport | Socket Mode (WebSocket, no public URL required) |
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) (health endpoint) |
| Database | SQLite via [SQLModel](https://sqlmodel.tiangolo.com/) + [aiosqlite](https://github.com/omnilib/aiosqlite) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) with per-plugin version directories |
| CLI | [Typer](https://typer.tiangolo.com/) |
| Configuration | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (environment variables) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |
| Type Checking | [ty](https://github.com/astral-sh/ty) |
| Testing | [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) |
| Pre-commit Hooks | [prek](https://github.com/kaleidawave/prek) |
| Task Runner | [just](https://github.com/casey/just) |

## Quick Start

### Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager
- A Slack workspace where you can create apps

### 1. Clone and Install

```bash
git clone <repo-url> kennabot
cd kennabot
uv sync
```

### 2. Create a Slack App

Go to [https://api.slack.com/apps](https://api.slack.com/apps) and create a new app. You can use the manifest below to configure it automatically.

<details>
<summary>Slack App Manifest (YAML)</summary>

```yaml
display_information:
  name: KennaBot
  description: Karma tracking and more
  background_color: "#2c2d30"
features:
  bot_user:
    display_name: KennaBot
    always_online: true
  slash_commands:
    - command: /plusplus
      description: Karma tracking commands
      usage_hint: "[@user | thing | top N | bottom N | erase name | help]"
      should_escape: false
oauth_config:
  scopes:
    bot:
      - channels:history
      - groups:history
      - im:history
      - mpim:history
      - chat:write
      - commands
      - users:read
settings:
  event_subscriptions:
    bot_events:
      - message.channels
      - message.groups
      - message.im
      - message.mpim
  interactivity:
    is_enabled: false
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

</details>

After creating the app:

1. **Install to workspace** under *Install App*.
2. **Copy the Bot User OAuth Token** (`xoxb-...`) from *OAuth & Permissions*.
3. **Generate an App-Level Token** under *Basic Information > App-Level Tokens*. Give it the `connections:write` scope. Copy the token (`xapp-...`).

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in the two required tokens:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

### 4. Start the Bot

```bash
# Using the CLI
kennabot serve

# Or with uv run
uv run kennabot serve
```

On first start, KennaBot automatically creates the database and runs all Alembic migrations. No separate `db init` step is required.

## Configuration

All configuration is via environment variables. Slack tokens use the standard `SLACK_*` names. All other settings use the `KENNABOT_` prefix.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | Yes | — | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Yes | — | App-Level Token for Socket Mode (`xapp-...`) |
| `KENNABOT_DB_PATH` | No | `./data/kennabot.db` | Path to the SQLite database file |
| `KENNABOT_ENABLED_PLUGINS` | No | *(all)* | Comma-separated list of plugin names to load (e.g. `plusplus`). When empty, all discovered plugins are loaded. |
| `KENNABOT_ADMIN_USERS` | No | *(empty)* | Comma-separated Slack user IDs who can erase scores |
| `KENNABOT_COOLDOWN_SECONDS` | No | `5` | Seconds between votes from the same user to the same target |
| `KENNABOT_REASON_CONJUNCTIONS` | No | `for,because,cause,cuz,as` | Words that introduce a reason in `thing++ for <reason>` |
| `KENNABOT_USE_DISPLAY_NAME` | No | `false` | Use display name (real name) instead of username for score storage |
| `KENNABOT_LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

You can inspect the active configuration with:

```bash
kennabot config show
```

Or validate that tokens and connectivity are working:

```bash
kennabot config validate
```

## CLI Reference

KennaBot includes a full management CLI. Run `kennabot --help` to see all commands.

### Core Commands

```
kennabot --version                    Show version
kennabot serve                        Start the bot
kennabot serve --port 9090            Start with a custom health endpoint port
kennabot serve --log-level DEBUG      Start with debug logging
```

### Database Management

```
kennabot db init                      Create the database and run all pending migrations
kennabot db migrate                   Apply any pending Alembic migrations (upgrade heads)
kennabot db revision -m "description" --plugin <name> --autogenerate
                                      Generate a new migration script for a plugin
kennabot db revision -m "description" --autogenerate
                                      Generate a new core migration script
```

### Configuration

```
kennabot config show                  Display config with redacted tokens
kennabot config validate              Check token formats, DB path, and Slack API connectivity
```

### Plugin Management

```
kennabot plugin list                  Show discovered plugins (plugins with CLI commands show [CLI])
```

### PlusPlus Commands

These commands are registered by the PlusPlus plugin and allow direct score management from the command line.

```
kennabot plusplus get <name>                    Look up score and reasons
kennabot plusplus top --limit 10               Show top 10 scores
kennabot plusplus bottom --limit 10            Show bottom 10 scores
kennabot plusplus set <name> <pts> --force     Manually set a score (requires --force)
kennabot plusplus erase <name>                 Delete all scores for an entity
kennabot plusplus erase <name> -r "reason"     Delete a specific reason only
kennabot plusplus stats                        Show row counts and file size
kennabot plusplus export -o scores.json        Export all scores to JSON
```

#### Importing from Hubot

If you're migrating from hubot-plusplus, you can import existing scores:

```bash
# From a JSON dump of the Hubot brain (e.g., redis-cli GET hubot:storage > dump.json)
kennabot plusplus import-hubot --from-file dump.json

# Directly from a running Redis instance
kennabot plusplus import-hubot --redis-url redis://localhost:6379

# Preview what would be imported without writing
kennabot plusplus import-hubot --from-file dump.json --dry-run
```

The Redis import requires the optional `redis` package:

```bash
uv pip install 'kennabot[import]'
```

## PlusPlus — Slack Usage

Once the bot is running and invited to a channel, users can give or take points using these patterns.

### Inline Message Patterns

| Pattern | Example | Effect |
|---------|---------|--------|
| `@user++` | `@molly++` | Add 1 point to molly |
| `@user--` | `@andy--` | Remove 1 point from andy |
| `thing++` | `pizza++` | Add 1 point to "pizza" |
| `thing--` | `meetings--` | Remove 1 point from "meetings" |
| `@user++ for <reason>` | `@molly++ for fixing the build` | Add 1 point with a tracked reason |
| `thing-- because <reason>` | `meetings-- because too many` | Remove 1 point with a reason |
| `thing—` | `bugs—` | Remove 1 point (em-dash from mobile keyboards) |
| `++` or `--` | `++` | Apply to the last voted thing in this channel or thread (MRU) |

Reason conjunctions are configurable. The defaults are: **for**, **because**, **cause**, **cuz**, **as**.

### Thread Awareness

KennaBot is thread-aware. Votes and MRU (most recently used) tracking are scoped independently between the main channel and threads:

- A `++` or `--` in a thread applies to the last thing voted on **in that thread**.
- A bare `++` in a thread will fall back to the channel MRU if no thread MRU exists.
- Votes in a thread do **not** overwrite the channel's MRU.
- Bot responses to thread votes are posted **in the thread**, not the main channel.

### Slash Command: `/plusplus`

| Command | Description |
|---------|-------------|
| `/plusplus @user` or `/plusplus thing` | Show score and top reasons |
| `/plusplus top [N]` | Leaderboard (default 10, max 50) |
| `/plusplus bottom [N]` | Bottom scores |
| `/plusplus erase <name> [for <reason>]` | Delete scores (admin only) |
| `/plusplus help` | Show help text |

### Rules

- **Self-vote prevention** — You cannot `++` or `--` yourself, whether by @mention or plain text username.
- **Spam prevention** — A configurable cooldown (default 5 seconds) prevents the same user from voting on the same target repeatedly.
- **Username vs. Display Name** — By default, scores are stored under the Slack username (e.g., "andy"). Set `KENNABOT_USE_DISPLAY_NAME=true` to use display names (e.g., "Andy George") instead.
- **Admin-gated erase** — If `KENNABOT_ADMIN_USERS` is set, only those users can use `/plusplus erase`. If empty, anyone can erase (not recommended for production).

### Response Examples

```
# Increment
@molly has 43 points (+1). 15 points are for fixing bugs.

# Decrement
meetings has -5 points (-1).

# Self-vote attempt
Nice try, @andy. You can't give yourself points.

# Score lookup (/plusplus @molly)
molly has 43 points.
Top reasons:
  fixing bugs: 15
  code reviews: 8
  helping onboard: 5

# Leaderboard (/plusplus top 5)
Top 5:
1. molly — 43 points
2. pizza — 38 points
3. andy — 22 points
4. python — 15 points
5. teamwork — 12 points
```

## Project Structure

```
kennabot/
├── alembic.ini                        Alembic configuration (version locations, DB URL)
├── Dockerfile                         Multi-stage container build
├── .dockerignore
├── .env.example                       Environment variable template
├── pyproject.toml                     Project metadata and dependencies
├── uv.lock                            Locked dependency versions
├── scripts/
│   └── import_redis.py                Legacy shim (points to CLI)
├── src/kennabot/
│   ├── __init__.py                    Package version
│   ├── __main__.py                    python -m kennabot support
│   ├── main.py                        Core async startup (Socket Mode + uvicorn)
│   ├── config.py                      Settings via pydantic-settings
│   ├── app.py                         Slack Bolt AsyncApp + FastAPI setup
│   ├── database.py                    Async engine, session factory, Alembic runner
│   ├── migrations/                    Core Alembic environment
│   │   ├── env.py                     Async migration env (discovers plugin version dirs)
│   │   ├── script.py.mako             Migration script template
│   │   └── versions/                  Core migration scripts (schema not owned by any plugin)
│   ├── models/
│   │   └── __init__.py                Central model registry (imports all plugin models)
│   ├── cli/
│   │   ├── __init__.py                Root Typer app, plugin CLI discovery
│   │   ├── async_typer.py             AsyncTyper subclass for async commands
│   │   ├── serve.py                   kennabot serve
│   │   ├── db.py                      kennabot db init/migrate/revision
│   │   ├── config_cmd.py              kennabot config show/validate
│   │   └── plugin_cmd.py              kennabot plugin list
│   └── plugins/
│       ├── __init__.py                Plugin auto-discovery, loader, duplicate-name guard
│       ├── base.py                    BasePlugin abstract class + validate_table_prefix()
│       └── plusplus/
│           ├── __init__.py
│           ├── plugin.py              Registers Slack listeners + CLI commands
│           ├── handlers.py            Message pattern matching + slash commands
│           ├── scorekeeper.py         Score business logic
│           ├── helpers.py             Name parsing, validation, formatting
│           ├── models.py              plugin_plusplus_* SQLModel table definitions
│           ├── cli.py                 kennabot plusplus CLI commands
│           └── migrations/
│               └── versions/          PlusPlus migration scripts
└── tests/
    ├── conftest.py                    Shared fixtures (test DB, settings)
    ├── test_cli.py                    CLI integration tests
    ├── test_plugin_loader.py          Plugin discovery + duplicate-name guard tests
    └── plugins/
        └── plusplus/
            ├── conftest.py            Plugin-specific fixtures (handlers, mock_client)
            ├── test_handlers.py       Slack handler + thread-awareness tests
            ├── test_helpers.py        Helper function tests
            └── test_scorekeeper.py   Score logic + MRU + thread tests
```

## Plugin System

KennaBot uses a plugin architecture where each plugin is a Python package under `src/kennabot/plugins/`. Plugins are automatically discovered at startup.

### Plugin Loading

At startup the loader:

1. Scans `src/kennabot/plugins/` for sub-packages that contain a `plugin.py` with a `BasePlugin` subclass.
2. Filters the discovered list against `KENNABOT_ENABLED_PLUGINS` (when set).
3. **Guards against duplicate names** — if two plugins declare the same `name`, KennaBot logs a `CRITICAL` error and refuses to start.
4. Imports each plugin's `models` module (if present) so SQLModel metadata is populated.
5. **Validates table prefixes** — every table in a plugin's `models.py` must start with `plugin_<name>_`. A violation raises an error and the plugin is skipped.
6. Calls `register()` to attach Slack event listeners and slash command handlers.

### Table Naming Convention

Every database table owned by a plugin **must** be prefixed with `plugin_<name>_`. This prevents table name collisions between plugins and core schema.

| Plugin | Required prefix | Example table |
|--------|----------------|---------------|
| `plusplus` | `plugin_plusplus_` | `plugin_plusplus_scores` |
| `myplugin` | `plugin_myplugin_` | `plugin_myplugin_widgets` |

The prefix is declared via the `table_prefix` abstract property on `BasePlugin` and is enforced at load time.

### Creating a New Plugin

1. Create a directory: `src/kennabot/plugins/myplugin/`
2. Add `plugin.py` with a `BasePlugin` subclass implementing `name`, `description`, `table_prefix`, and `register()`.
3. If the plugin needs database tables, add `models.py` with `SQLModel` classes whose `__tablename__` starts with `plugin_myplugin_`.
4. Import the models in `src/kennabot/models/__init__.py` so they are registered with SQLModel metadata.
5. Create `migrations/versions/` inside the plugin directory.
6. Add the versions path to `alembic.ini` under `version_locations`.
7. Generate the initial migration: `kennabot db revision --plugin myplugin --autogenerate -m "initial tables"`
8. Optionally implement `register_cli()` to add `kennabot myplugin` subcommands.

```python
# src/kennabot/plugins/myplugin/plugin.py

from kennabot.plugins.base import BasePlugin


class MyPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "myplugin"

    @property
    def description(self) -> str:
        return "Does something cool"

    @property
    def table_prefix(self) -> str:
        return "plugin_myplugin_"

    async def register(self, app, session_factory, settings) -> None:
        @app.event("message")
        async def on_message(event, say, client):
            pass

    def register_cli(self, parent_app) -> None:
        from kennabot.cli.async_typer import AsyncTyper

        my_app = AsyncTyper(name="myplugin", help="My plugin commands.")

        @my_app.command()
        def hello() -> None:
            """Say hello."""
            print("Hello from myplugin!")

        parent_app.add_typer(my_app, name="myplugin")
```

### BasePlugin Interface

| Member | Required | Description |
|--------|----------|-------------|
| `name` (property) | Yes | Short identifier (e.g., `"plusplus"`). Must be unique across all loaded plugins. |
| `description` (property) | Yes | Human-readable description shown in `kennabot plugin list`. |
| `table_prefix` (property) | Yes | Required prefix for all plugin-owned DB tables (e.g., `"plugin_plusplus_"`). Enforced at load time. |
| `register(app, session_factory, settings)` | Yes | Register Slack event listeners and slash command handlers. |
| `register_cli(parent_app)` | No | Register CLI subcommands under `kennabot <name>`. |

## Database

KennaBot uses SQLite for storage, accessed asynchronously via SQLModel and aiosqlite. Schema is managed by Alembic.

### Migrations

Alembic migrations run automatically when KennaBot starts (`alembic upgrade heads`). The migration environment (`src/kennabot/migrations/env.py`) discovers version directories from all enabled plugins at runtime, so only the migrations relevant to the active set of plugins are applied.

**Workflow for schema changes:**

```bash
# Add a table to an existing plugin
kennabot db revision --plugin plusplus --autogenerate -m "add widget column"

# Apply pending migrations manually (also runs automatically on serve)
kennabot db migrate

# Check current migration state
uv run alembic current

# View migration history
uv run alembic history
```

Migration scripts are stored per-plugin under `src/kennabot/plugins/<name>/migrations/versions/`. Core migrations (not owned by any plugin) live in `src/kennabot/migrations/versions/`.

### PlusPlus Schema

All PlusPlus tables are prefixed with `plugin_plusplus_`.

**`plugin_plusplus_scores`** — Main score tracking

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT, UNIQUE | Normalized lowercase entity name |
| `score` | INTEGER | Current total score |
| `is_user` | BOOLEAN | Whether this is a Slack user (vs. arbitrary thing) |
| `slack_user_id` | TEXT, NULLABLE | Slack user ID if applicable |
| `created_at` | DATETIME | First score event |
| `updated_at` | DATETIME | Last score change |

**`plugin_plusplus_score_reasons`** — Per-reason point breakdown

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `score_id` | INTEGER FK | References `plugin_plusplus_scores.id` |
| `reason` | TEXT | Normalized reason text |
| `points` | INTEGER | Net points for this reason |
| UNIQUE | `(score_id, reason)` | One entry per reason per entity |

**`plugin_plusplus_score_log`** — Audit log and spam prevention

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `from_user_id` | TEXT | Slack user ID of the voter |
| `to_name` | TEXT | Normalized target name |
| `direction` | TEXT | `"++"` or `"--"` |
| `reason` | TEXT, NULLABLE | Optional reason text |
| `channel_id` | TEXT | Slack channel ID |
| `created_at` | DATETIME | Timestamp of the vote |

### Backup and Export

```bash
# Export PlusPlus scores to a portable JSON file
kennabot plusplus export -o backup.json

# Copy the SQLite file directly (stop the bot first for a clean copy)
cp ./data/kennabot.db ./backups/kennabot-$(date +%Y%m%d).db
```

See the [Container Deployment](#container-deployment) section for backup
commands when running inside a Podman container.

## Container Deployment

KennaBot ships as a two-stage container image. The builder stage installs
dependencies with uv; the runtime stage is a minimal Python slim image running
as a non-root user (`kennabot`, UID 1000).

### Build

```bash
podman build -t kennabot .
```

> **Note:** Podman defaults to OCI image format, which does not honour the
> `HEALTHCHECK` instruction from the Dockerfile. The health check is configured
> instead via `--health-cmd` on `podman run` (shown below).

### Create the Data Volume

The database is stored in a named volume so it persists across container
restarts and image upgrades.

```bash
podman volume create kennabot_data
```

### Run

```bash
podman run -d \
  --name kennabot \
  --env-file .env \
  -v kennabot_data:/data \
  -p 8080:8080 \
  --health-cmd "kennabot healthcheck" \
  --health-interval 30s \
  --health-timeout 5s \
  --health-start-period 10s \
  --health-retries 3 \
  kennabot
```

The container:
- Runs as a non-root user (`kennabot`, UID 1000)
- Stores the database in the `kennabot_data` volume at `/data/kennabot.db`
- Exposes port 8080 for the health endpoint (`GET /health`)
- Runs Alembic migrations automatically on startup — no manual `db init` needed

### Check Container Status

```bash
# Overall status and health state
podman ps

# Detailed health check status
podman inspect kennabot --format '{{.State.Health.Status}}'

# Live log stream
podman logs -f kennabot
```

### Manage the Container

```bash
# Stop
podman stop kennabot

# Start again (migrations are a no-op when already at head)
podman start kennabot

# Restart
podman restart kennabot

# Remove (data volume is preserved)
podman rm kennabot
```

### Upgrade

```bash
# Pull or rebuild the new image
podman build -t kennabot .

# Replace the running container (volume keeps the database)
podman stop kennabot
podman rm kennabot
podman run -d \
  --name kennabot \
  --env-file .env \
  -v kennabot_data:/data \
  -p 8080:8080 \
  --health-cmd "kennabot healthcheck" \
  --health-interval 30s \
  --health-timeout 5s \
  --health-start-period 10s \
  --health-retries 3 \
  kennabot
```

Any pending Alembic migrations are applied automatically on the new container's
first startup.

### Container CLI Access

```bash
# List loaded plugins
podman exec kennabot kennabot plugin list

# Check scores
podman exec kennabot kennabot plusplus top

# Database stats
podman exec kennabot kennabot plusplus stats

# Validate configuration and Slack connectivity
podman exec kennabot kennabot config validate

# Check current Alembic migration state
podman exec kennabot alembic -c /app/alembic.ini current

# Import data from a Hubot brain dump
podman cp dump.json kennabot:/tmp/dump.json
podman exec kennabot kennabot plusplus import-hubot --from-file /tmp/dump.json
```

### Backup the Database

```bash
# Export scores to JSON
podman exec kennabot kennabot plusplus export -o /data/backup.json
podman cp kennabot:/data/backup.json ./backup.json

# Or copy the raw SQLite file
podman cp kennabot:/data/kennabot.db ./kennabot-$(date +%Y%m%d).db
```

## Development

### Setup

```bash
git clone <repo-url> kennabot
cd kennabot
uv sync --all-extras
```

### Run Tests

```bash
uv run pytest tests/ -v
```

### Lint and Type Check

```bash
uv run ruff check src/ tests/
uv run ruff check src/ tests/ --fix  # Auto-fix issues
uv run ruff format src/ tests/       # Apply formatting
uv run ty check src/ tests/

# Run all checks at once
uv run ruff check src/ tests/ && uv run ty check src/ tests/ && uv run pytest tests/ -v
```

### Pre-commit Hooks with prek

KennaBot uses [prek](https://github.com/kaleidawave/prek) to run lint, type
checking, and tests automatically before every commit.

**Install the hook** (one-time, per clone):

```bash
prek install
```

After this, every `git commit` automatically runs:

| Hook | Command | What it checks |
|------|---------|---------------|
| `ruff lint` | `uv run ruff check src/ tests/` | Linting and import order |
| `ruff format check` | `uv run ruff format --check src/ tests/` | Code formatting |
| `ty` | `uv run ty check src/ tests/` | Static type checking |
| `pytest` | `uv run pytest tests/ -q --tb=short` | Full test suite |

If any hook fails the commit is blocked. Fix the issue and commit again.

**Run hooks manually** without committing:

```bash
# Run all hooks against staged files
prek run

# Run all hooks against every file in the repo
prek run --all-files

# Run a single hook by ID
prek run --hook ty
prek run --hook pytest

# Auto-fix formatting then re-run
uv run ruff format src/ tests/
prek run --all-files
```

### Task Runner (just)

KennaBot ships a `Justfile` for common local tasks. Run `just` with no
arguments to list all available recipes.

**Container:**

```bash
just build          # Build the container image
just build-fresh    # Build with no layer cache
just volume         # Create the kennabot_data volume (idempotent)
just run            # Start the container with health check configured
just up             # build + run in one step
just down           # Stop and remove the container (data volume is preserved)
just restart        # down + up (rebuild and restart)
just logs           # Stream container logs (podman logs -f)
just status         # Show container status and health state
just healthcheck    # Run kennabot healthcheck inside the container
just shell          # Open an interactive shell inside the container
```

**Database (requires a running container):**

```bash
just db-stats               # Show PlusPlus row counts and file size
just db-export              # Export scores to scores.json and copy it out
just db-export file=out.json  # Export to a custom filename
just db-backup              # Copy kennabot.db out with a timestamp
```

**Development:**

```bash
just install    # uv sync --all-extras
just lint       # ruff check src/ tests/
just fmt        # ruff check --fix + ruff format (auto-fix everything)
just typecheck  # ty check src/ tests/
just test       # pytest tests/ -v
just check      # lint + typecheck + test in one step
just hooks      # prek install (one-time per clone)
```

### Run Locally

```bash
cp .env.example .env
# Edit .env with your Slack tokens
uv run kennabot serve
```

## Acknowledgements

KennaBot's design is heavily inspired by [Hubot](https://github.com/hubotio/hubot), GitHub's beloved chat bot framework, and the [hubot-plusplus](https://github.com/ajacksified/hubot-plusplus) plugin by Jack Lawson which brought karma tracking to countless Slack and HipChat workspaces. Thank you to all the contributors who built and maintained those projects.

## License

MIT License — Copyright (c) 2026 [QuickVM, LLC](https://quickvm.com).
See [LICENSE](LICENSE) for the full text.
