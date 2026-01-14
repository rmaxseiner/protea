# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir .

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies (for Pillow image processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwebp7 \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/inventory-* /usr/local/bin/

# Copy source and entrypoint
COPY src/ ./src/
COPY docker-entrypoint.sh /usr/local/bin/

RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create data directories
RUN mkdir -p /data/db /data/images && \
    chown -R appuser:appuser /app /data

# Switch to non-root user
USER appuser

# Environment variables with defaults
ENV INVENTORY_DATABASE_PATH=/data/db/inventory.db \
    INVENTORY_IMAGE_BASE_PATH=/data/images \
    INVENTORY_WEB_HOST=0.0.0.0 \
    INVENTORY_WEB_PORT=8080 \
    INVENTORY_MCP_SSE_HOST=0.0.0.0 \
    INVENTORY_MCP_SSE_PORT=8081

# Expose web UI and MCP SSE ports
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["web"]
