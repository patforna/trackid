FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir yt-dlp

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install the package
RUN uv sync --frozen --no-dev

# Create data directory
RUN mkdir -p /data

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV TRACKID_DATA_DIR=/data

# Default entrypoint
ENTRYPOINT ["trackid"]
CMD ["--help"]
