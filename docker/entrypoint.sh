#!/bin/bash
set -e

# Force Python to be unbuffered
export PYTHONUNBUFFERED=1

# Check for INDEX_MODE - run indexer instead of API
if [ "$INDEX_MODE" = "true" ]; then
    echo "=== INDEX MODE: Running indexer ==="

    # Create necessary directories
    mkdir -p /data/qdrant_storage /models_cache /var/log

    # Start Qdrant
    echo "Starting Qdrant..."
    mkdir -p /qdrant/config
    cp /app/config/qdrant.yaml /qdrant/config/config.yaml
    /usr/local/bin/qdrant --config-path /qdrant/config/config.yaml > /var/log/qdrant.log 2>&1 &

    # Wait for Qdrant
    echo "Waiting for Qdrant to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:6333/healthz > /dev/null 2>&1; then
            echo "Qdrant is ready after $i seconds!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "ERROR: Qdrant failed to start"
            cat /var/log/qdrant.log
            exit 1
        fi
        sleep 1
    done

    # Run indexer
    echo "Running indexer..."
    python /app/scripts/index.py

    echo "=== Indexing complete ==="
    exit 0
fi

echo "=== Starting IRE Resources Semantic Search services ==="
echo "Set PYTHONUNBUFFERED=1"

# Create necessary directories
mkdir -p /data/qdrant_storage /models_cache /var/log

# Debug: Show environment
echo "=== Environment Variables ==="
echo "PORT=${PORT:-8000}"
echo "LOG_LEVEL=${LOG_LEVEL:-info}"
echo "QDRANT_HOST=${QDRANT_HOST:-localhost}"
echo "QDRANT_PORT=${QDRANT_PORT:-6333}"
echo "MODEL_NAME=${MODEL_NAME:-all-MiniLM-L6-v2}"
echo "PYTHONPATH=${PYTHONPATH}"
echo "PATH=${PATH}"

# Debug: Check Python and dependencies
echo "=== Python Environment ==="
which python
python --version
echo "Python packages:"
python -c "import uvicorn; print(f'uvicorn version: {uvicorn.__version__}')" || echo "Failed to import uvicorn"
python -c "import fastapi; print(f'fastapi version: {fastapi.__version__}')" || echo "Failed to import fastapi"

# Debug: Test if FastAPI app can be imported
echo "=== Testing FastAPI App Import ==="
python -c "
import sys
sys.path.insert(0, '/app')
print('Python path:', sys.path)
try:
    from app.main import app
    print('SUCCESS: FastAPI app imported successfully')
    print(f'App type: {type(app)}')
except Exception as e:
    print(f'ERROR importing FastAPI app: {e}')
    import traceback
    traceback.print_exc()
"

# Check if Qdrant binary exists
echo "=== Qdrant Setup ==="
if [ ! -f /usr/local/bin/qdrant ]; then
    echo "ERROR: Qdrant binary not found at /usr/local/bin/qdrant"
    exit 1
fi

echo "Qdrant binary found:"
ls -la /usr/local/bin/qdrant
/usr/local/bin/qdrant --version || echo "Failed to get Qdrant version"

# Copy configuration file to Qdrant's expected location
mkdir -p /qdrant/config
cp /app/config/qdrant.yaml /qdrant/config/config.yaml

# Start Qdrant
echo "=== Starting Qdrant ==="
/usr/local/bin/qdrant \
    --config-path /qdrant/config/config.yaml \
    > /var/log/qdrant.log 2>&1 &

QDRANT_PID=$!
echo "Qdrant started with PID: $QDRANT_PID"

# Wait for Qdrant
echo "Waiting for Qdrant to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:6333/healthz > /dev/null 2>&1; then
        echo "Qdrant is ready after $i seconds!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Qdrant failed to start"
        cat /var/log/qdrant.log
        exit 1
    fi
    sleep 1
done

# Start FastAPI with lots of debugging
echo "=== Starting FastAPI Application ==="
echo "Command: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level debug"

# Run uvicorn once (avoid double-start warmup to reduce boot time)
python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --log-level debug \
    --access-log \
    --use-colors
