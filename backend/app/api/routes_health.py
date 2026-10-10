from fastapi import APIRouter
from ..models.schema import HealthResponse
from ..services.qdrant_service import QdrantService
from ..services.manifest_service import ManifestService
from ..config import GROQ_API_KEY, TRANSCRIPT_DIR, CHUNK_DIR

router = APIRouter(tags=["Health & Status"])

@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
def health_check():
    qdrant_service = QdrantService.get_instance()
    points_count = qdrant_service.get_points_count()
    
    transcripts_count = len(list(TRANSCRIPT_DIR.glob("*.json"))) if TRANSCRIPT_DIR.exists() else 0
    chunks_count = len(list(CHUNK_DIR.glob("*.json"))) if CHUNK_DIR.exists() else 0

    return HealthResponse(
        status="healthy",
        backend_version="0.2.0",
        whisper_ready=True,
        embeddings_ready=True,
        qdrant_ready=True,
        groq_ready=bool(GROQ_API_KEY),
        total_indexed_points=points_count,
        total_transcripts=transcripts_count,
        total_chunks=chunks_count,
    )

@router.get("/api")
@router.get("/api/info")
def api_info():
    return {
        "status": "online",
        "service": "YT Reviser API",
        "version": "0.2.0",
        "docs_url": "/docs",
    }

