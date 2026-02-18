# KennaBot — local development tasks
# https://github.com/casey/just

image := "kennabot"
registry := "ghcr.io/quickvm/kennabot"
data_volume := "kennabot_data"
env_file := ".env"
port := "8080"

# List available recipes
default:
    @just --list

# ── Container ────────────────────────────────────────────────────────────────

# Build the container image
build:
    podman build -t {{ image }} .

# Build with no layer cache
build-fresh:
    podman build --no-cache -t {{ image }} .

# Create the persistent data volume (idempotent)
volume:
    podman volume create {{ data_volume }} 2>/dev/null || true

# Start the container
run: volume
    podman run -d \
        --name {{ image }} \
        --env-file {{ env_file }} \
        -v {{ data_volume }}:/data \
        -p {{ port }}:8080 \
        --health-cmd "kennabot healthcheck" \
        --health-interval 30s \
        --health-timeout 5s \
        --health-start-period 10s \
        --health-retries 3 \
        {{ image }}

# Build then start the container
up: build run

# Stop and remove the container (data volume is preserved)
down:
    podman stop {{ image }} 2>/dev/null || true
    podman rm {{ image }} 2>/dev/null || true

# Stop, remove, rebuild, and restart
restart: down up

# Stream container logs
logs:
    podman logs -f {{ image }}

# Check container status and health
status:
    @podman inspect {{ image }} --format 'Status: {{{{.State.Status}}  Health: {{{{.State.Health.Status}}' 2>/dev/null || echo "Container '{{ image }}' is not running"

# Run kennabot healthcheck against the running container
healthcheck:
    podman exec {{ image }} kennabot healthcheck

# Open a shell inside the running container
shell:
    podman exec -it {{ image }} /bin/bash

# ── Database ─────────────────────────────────────────────────────────────────

# Show PlusPlus database statistics
db-stats:
    podman exec {{ image }} kennabot plusplus stats

# Export scores to JSON
db-export file="scores.json":
    podman exec {{ image }} kennabot plusplus export -o /data/{{ file }}
    podman cp {{ image }}:/data/{{ file }} ./{{ file }}
    @echo "Exported to ./{{ file }}"

# Copy the raw SQLite database file out of the container
db-backup:
    podman cp {{ image }}:/data/kennabot.db ./kennabot-$(date +%Y%m%d-%H%M%S).db
    @echo "Backup complete"

# ── Development ──────────────────────────────────────────────────────────────

# Install dependencies
install:
    uv sync --all-extras

# Run linter
lint:
    uv run ruff check src/ tests/

# Auto-fix lint issues and apply formatting
fmt:
    uv run ruff check src/ tests/ --fix
    uv run ruff format src/ tests/

# Run type checker
typecheck:
    uv run ty check src/ tests/

# Run tests
test:
    uv run pytest tests/ -v

# Run all checks (lint + types + tests)
check: lint typecheck test

# Install prek pre-commit hooks
hooks:
    prek install
