from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class VideoStage(str):
    DISCOVERED = "discovered"
    AUDIO_DOWNLOADED = "audio_downloaded"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    CHUNKING_COMPLETED = "chunking_completed"
    EMBEDDINGS_GENERATED = "embeddings_generated"
    UPLOADED_TO_QDRANT = "uploaded_to_qdrant"
    FULLY_COMPLETED = "fully_completed"
    FAILED = "failed"

class VideoManifestEntry(BaseModel):
    video_id: str
    title: str
    duration: float = 0.0
    original_url: str
    playlist_id: Optional[str] = None
    playlist_title: Optional[str] = None
    status: str = "discovered"  # discovered, in_progress, completed, failed, skipped
    stage: str = VideoStage.DISCOVERED
    error: Optional[str] = None
    audio_path: Optional[str] = None
    transcript_path: Optional[str] = None
    chunk_path: Optional[str] = None
    chunk_count: int = 0
    language: str = "en"
    whisper_model: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class PlaylistManifestEntry(BaseModel):
    playlist_id: str
    title: str
    url: str
    video_ids: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_synced_at: Optional[str] = None

class IngestionManifest(BaseModel):
    version: str = "1.0"
    videos: Dict[str, VideoManifestEntry] = Field(default_factory=dict)
    playlists: Dict[str, PlaylistManifestEntry] = Field(default_factory=dict)
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
