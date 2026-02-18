# Stage 1: Build dependencies with uv
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev extras)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and Alembic config
COPY src/ src/
COPY alembic.ini ./

# Install the project itself
RUN uv sync --frozen --no-dev


# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment, source, and Alembic config from the builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Ensure the venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create a non-root user
RUN groupadd --gid 1000 kennabot && \
    useradd --uid 1000 --gid kennabot --shell /bin/bash --create-home kennabot

# Create data directory for the SQLite database
RUN mkdir -p /data && chown kennabot:kennabot /data

# Switch to non-root user
USER kennabot

# Database volume
VOLUME ["/data"]

# Environment defaults
ENV KENNABOT_DB_PATH=/data/kennabot.db
ENV KENNABOT_LOG_LEVEL=INFO

# Health check against the FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["kennabot", "healthcheck"]

EXPOSE 8080

CMD ["kennabot", "serve"]
