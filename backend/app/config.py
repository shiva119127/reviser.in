import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

# LLM & Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Embeddings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = 384

# Whisper
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

def _clean_str(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "undefined", "false", '""', "''"):
        return None
    return s

# Qdrant
QDRANT_PATH = os.getenv("QDRANT_PATH", str(ROOT_DIR / "qdrant_db"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "yt_reviser")
QDRANT_URL = _clean_str(os.getenv("QDRANT_URL", None))
QDRANT_API_KEY = _clean_str(os.getenv("QDRANT_API_KEY", None))

# Storage Paths
DATA_DIR = ROOT_DIR / "data"
AUDIO_DIR = Path(os.getenv("AUDIO_DIR", str(DATA_DIR / "audio")))
TRANSCRIPT_DIR = Path(os.getenv("TRANSCRIPT_DIR", str(DATA_DIR / "transcripts")))
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", str(DATA_DIR / "chunks")))
MANIFEST_PATH = Path(os.getenv("MANIFEST_PATH", str(DATA_DIR / "manifest.json")))

# Frontend Origin for CORS
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# Chunking Configuration
TARGET_CHUNK_DURATION = 75.0  # seconds

# Ensure required directories exist
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
CHUNK_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
