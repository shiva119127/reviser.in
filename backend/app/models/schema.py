from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Transcript Models
class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

class TranscriptData(BaseModel):
    video_id: str
    title: str
    language: str = "en"
    model: str = "small"
    duration: float = 0.0
    segments: List[TranscriptSegment] = Field(default_factory=list)

# Chunk Models
class ChunkData(BaseModel):
    chunk_id: str
    video_id: str
    title: str
    duration: float = 0.0
    start: float
    end: float
    text: str
    playlist_id: Optional[str] = None
    language: str = "en"
    youtube_url: str
    timestamped_url: str

# API Ingest Request / Response
class IngestRequest(BaseModel):
    url: str
    force_reprocess: bool = False

class VideoJobSummary(BaseModel):
    video_id: str
    title: str
    duration: float = 0.0
    status: str
    stage: str
    error: Optional[str] = None

class IngestJobResponse(BaseModel):
    job_id: str
    url: str
    is_playlist: bool = False
    playlist_id: Optional[str] = None
    playlist_title: Optional[str] = None
    status: str
    total_videos: int = 0
    completed_videos: int = 0
    skipped_videos: int = 0
    failed_videos: int = 0
    current_stage: str = "idle"
    current_video_id: Optional[str] = None
    current_video_title: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None
    videos: List[VideoJobSummary] = Field(default_factory=list)

# API Chat / Q&A Models
class ChatRequest(BaseModel):
    question: str
    playlist_id: Optional[str] = None
    video_id: Optional[str] = None
    top_k: int = 5

class QuestionRequest(BaseModel):
    """Backwards compatibility with original frontend /api/ask"""
    question: str

class SourceCitation(BaseModel):
    video_id: str
    title: str
    start: float
    end: float
    text: str
    youtube_url: str
    timestamped_url: str
    score: float = 0.0

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)

# Playlist Models
class PlaylistSummary(BaseModel):
    playlist_id: str
    title: str
    url: str
    total_videos: int = 0
    indexed_videos: int = 0
    last_synced_at: Optional[str] = None

# Health Check Model
class HealthResponse(BaseModel):
    status: str
    backend_version: str
    whisper_ready: bool
    embeddings_ready: bool
    qdrant_ready: bool
    groq_ready: bool
    total_indexed_points: int = 0
    total_transcripts: int = 0
    total_chunks: int = 0
