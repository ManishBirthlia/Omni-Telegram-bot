# ── Stage 1: Build dependencies ──────────────────────────
FROM python:3.14-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache-friendly)
COPY pyproject.toml uv.lock ./

# Install dependencies into .venv using uv
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: Runtime ─────────────────────────────────────
FROM python:3.14-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -r appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY . .

# Make sure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create download directories
RUN mkdir -p "Youtube Downloads" "Instagram Downloads" "Generated Images" "S3 Storage" \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose Prometheus metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import asyncio; asyncio.run(__import__('asyncio').sleep(0))" || exit 1

# Default command (run the telegram bot)
CMD ["python", "-m", "bot.main"]
