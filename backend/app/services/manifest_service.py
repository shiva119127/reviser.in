import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from ..config import MANIFEST_PATH, TRANSCRIPT_DIR, CHUNK_DIR
from ..models.manifest import (
    IngestionManifest,
    VideoManifestEntry,
    PlaylistManifestEntry,
    VideoStage,
)
from ..utils.logger import logger

class ManifestService:
    _instance = None
    _lock = threading.RLock()

    def __init__(self, manifest_path: Path = MANIFEST_PATH):
        self.manifest_path = manifest_path
        self._manifest: Optional[IngestionManifest] = None
        self._load()

    @classmethod
    def get_instance(cls) -> "ManifestService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ManifestService()
            return cls._instance

    def _load(self):
        with self._lock:
            if self.manifest_path.exists():
                try:
                    with open(self.manifest_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._manifest = IngestionManifest.model_validate(data)
                        logger.info(f"Loaded manifest with {len(self._manifest.videos)} videos and {len(self._manifest.playlists)} playlists.")
                        return
                except Exception as e:
                    logger.error(f"Error loading manifest file {self.manifest_path}: {e}")
            
            # Initialize empty manifest
            self._manifest = IngestionManifest()
            self._bootstrap_from_existing_files()
            self._save_locked()

    def _bootstrap_from_existing_files(self):
        """Discovers existing transcript and chunk files and populates manifest."""
        logger.info("Bootstrapping manifest from existing disk files...")
        if not TRANSCRIPT_DIR.exists():
            return

        for transcript_file in TRANSCRIPT_DIR.glob("*.json"):
            video_id = transcript_file.stem
            try:
                with open(transcript_file, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                    title = t_data.get("title", f"Video {video_id}")
                    duration = float(t_data.get("duration", 0.0))
                    language = t_data.get("language", "en")
                    whisper_model = t_data.get("model", "unknown")

                chunk_file = CHUNK_DIR / f"{video_id}.json"
                chunk_count = 0
                stage = VideoStage.TRANSCRIPTION_COMPLETED
                status = "completed"

                if chunk_file.exists():
                    try:
                        with open(chunk_file, "r", encoding="utf-8") as cf:
                            c_data = json.load(cf)
                            chunk_count = len(c_data) if isinstance(c_data, list) else 0
                            stage = VideoStage.FULLY_COMPLETED
                    except Exception:
                        pass

                entry = VideoManifestEntry(
                    video_id=video_id,
                    title=title,
                    duration=duration,
                    original_url=f"https://www.youtube.com/watch?v={video_id}",
                    status=status,
                    stage=stage,
                    transcript_path=str(transcript_file),
                    chunk_path=str(chunk_file) if chunk_file.exists() else None,
                    chunk_count=chunk_count,
                    language=language,
                    whisper_model=whisper_model,
                )
                self._manifest.videos[video_id] = entry
            except Exception as e:
                logger.warning(f"Could not bootstrap {transcript_file}: {e}")

        logger.info(f"Bootstrapped {len(self._manifest.videos)} existing videos into manifest.")

    def _save_locked(self):
        self._manifest.last_updated = datetime.utcnow().isoformat()
        temp_path = self.manifest_path.with_suffix(".tmp")
        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest.model_dump(), f, indent=2, ensure_ascii=False)
            temp_path.replace(self.manifest_path)
        except Exception as e:
            logger.error(f"Failed to save manifest atomically: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def get_manifest(self) -> IngestionManifest:
        with self._lock:
            return self._manifest

    def get_video(self, video_id: str) -> Optional[VideoManifestEntry]:
        with self._lock:
            return self._manifest.videos.get(video_id)

    def is_video_completed(self, video_id: str) -> bool:
        with self._lock:
            entry = self._manifest.videos.get(video_id)
            if entry and entry.stage in (VideoStage.FULLY_COMPLETED, VideoStage.UPLOADED_TO_QDRANT) and entry.status == "completed":
                # Also verify transcript file actually exists
                if entry.transcript_path and Path(entry.transcript_path).exists():
                    return True
            return False

    def register_video(self, video_id: str, title: str, original_url: str, duration: float = 0.0, playlist_id: Optional[str] = None, playlist_title: Optional[str] = None) -> VideoManifestEntry:
        with self._lock:
            if video_id in self._manifest.videos:
                entry = self._manifest.videos[video_id]
                entry.title = title or entry.title
                entry.duration = duration or entry.duration
                if playlist_id:
                    entry.playlist_id = playlist_id
                if playlist_title:
                    entry.playlist_title = playlist_title
                entry.updated_at = datetime.utcnow().isoformat()
            else:
                entry = VideoManifestEntry(
                    video_id=video_id,
                    title=title,
                    duration=duration,
                    original_url=original_url,
                    playlist_id=playlist_id,
                    playlist_title=playlist_title,
                    status="discovered",
                    stage=VideoStage.DISCOVERED,
                )
                self._manifest.videos[video_id] = entry
            self._save_locked()
            return entry

    def update_video_stage(
        self,
        video_id: str,
        stage: str,
        status: str = "in_progress",
        error: Optional[str] = None,
        audio_path: Optional[str] = None,
        transcript_path: Optional[str] = None,
        chunk_path: Optional[str] = None,
        chunk_count: Optional[int] = None,
        language: Optional[str] = None,
        whisper_model: Optional[str] = None,
        duration: Optional[float] = None,
    ):
        with self._lock:
            if video_id not in self._manifest.videos:
                return
            entry = self._manifest.videos[video_id]
            entry.stage = stage
            entry.status = status
            entry.error = error
            if audio_path is not None:
                entry.audio_path = audio_path
            if transcript_path is not None:
                entry.transcript_path = transcript_path
            if chunk_path is not None:
                entry.chunk_path = chunk_path
            if chunk_count is not None:
                entry.chunk_count = chunk_count
            if language is not None:
                entry.language = language
            if whisper_model is not None:
                entry.whisper_model = whisper_model
            if duration is not None:
                entry.duration = duration
            entry.updated_at = datetime.utcnow().isoformat()
            self._save_locked()

    def register_playlist(self, playlist_id: str, title: str, url: str, video_ids: List[str]):
        with self._lock:
            self._manifest.playlists[playlist_id] = PlaylistManifestEntry(
                playlist_id=playlist_id,
                title=title,
                url=url,
                video_ids=video_ids,
                last_synced_at=datetime.utcnow().isoformat(),
            )
            self._save_locked()

    def list_playlists(self) -> List[PlaylistManifestEntry]:
        with self._lock:
            return list(self._manifest.playlists.values())

    def get_playlist(self, playlist_id: str) -> Optional[PlaylistManifestEntry]:
        with self._lock:
            return self._manifest.playlists.get(playlist_id)
