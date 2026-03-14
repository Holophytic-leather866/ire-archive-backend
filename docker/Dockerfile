# Multi-stage build for IRE Resources Semantic Search
# syntax=docker/dockerfile:1.4

# Stage 1: Model builder (uses pre-built base image with ML dependencies)
# Base image contains: sentence-transformers==5.1.1, fastembed==0.7.3, optimum==2.0.0
# To update base image: make prod-build-base ARGS="--tag v1.0.0"
FROM ghcr.io/ireapps/ire-ml-base:v1.0.0 as model-builder

WORKDIR /app

# Download the cross-encoder model to /models_cache (persists in image)
# Note: Bi-encoder (all-MiniLM-L6-v2) downloads automatically via sentence-transformers
RUN mkdir -p /models_cache && \
    SENTENCE_TRANSFORMERS_HOME=/models_cache python -c "from sentence_transformers import CrossEncoder; \
    reranker = CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2', max_length=256, device='cpu', backend='onnx'); \
    print('Cross-encoder model downloaded successfully')"

# Stage 2: Dependency builder (separate for better caching)
FROM python:3.12-slim as dependency-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    pip install uv && \
    uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system -r requirements.txt && \
    rm requirements.txt

# Production stage
FROM python:3.12-slim

# Install runtime dependencies and Qdrant
RUN apt-get update && apt-get install -y \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Qdrant binary v1.16.0
RUN curl -L https://github.com/qdrant/qdrant/releases/download/v1.16.0/qdrant-x86_64-unknown-linux-gnu.tar.gz -o /tmp/qdrant.tar.gz && \
    tar -xzf /tmp/qdrant.tar.gz -C /usr/local/bin/ && \
    chmod +x /usr/local/bin/qdrant && \
    rm -f /tmp/qdrant.tar.gz && \
    echo "Qdrant installed at:" && \
    ls -la /usr/local/bin/qdrant && \
    /usr/local/bin/qdrant --version

# Create necessary directories
RUN mkdir -p /app /data/qdrant_storage /models_cache /var/log/supervisor

# Copy Python packages from dependency builder (rarely changes)
COPY --from=dependency-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependency-builder /usr/local/bin /usr/local/bin

# Copy cached cross-encoder model from model-builder stage (avoids relying on repo context)
# - Bi-encoder (dense): Downloads automatically via sentence-transformers at runtime
# - Sparse (BM25): Downloads via fastembed to its own cache
# - Cross-encoder: Pre-fetched in model-builder stage for faster startup
COPY --from=model-builder /models_cache /models_cache

# Set working directory
WORKDIR /app

# Copy configuration files (changes rarely)
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy application code LAST (changes most frequently)
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY docker/config/qdrant.yaml ./config/qdrant.yaml

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    QDRANT_HOST=localhost \
    QDRANT_PORT=6333 \
    MODEL_CACHE_DIR=/models_cache

# Expose ports
EXPOSE 8000 6333

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Use supervisor to run both services
CMD ["/entrypoint.sh"]
