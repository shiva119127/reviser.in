# Multi-stage / optimized Python build for YT Reviser Backend
FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
# Limit thread pools and memory fragmentation to fit comfortably within free 512MB RAM
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    TORCH_NUM_THREADS=1 \
    MALLOC_TRIM_THRESHOLD_=100000

# Install system dependencies including ffmpeg for audio processing and yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications
COPY requirements.txt ./

# Install CPU-only PyTorch and dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and cache embedding model during image build so runtime requests never download over network
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy backend code, data folder structure, pre-indexed vector DB, and frontend (as fallback static host)
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
COPY qdrant_db/ ./qdrant_db/

# Ensure all runtime storage directories exist and clean any stale lock files
RUN rm -f qdrant_db/.lock && \
    mkdir -p data/audio data/transcripts data/chunks qdrant_db

# Expose default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Start uvicorn server binding to 0.0.0.0 and dynamic PORT
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
