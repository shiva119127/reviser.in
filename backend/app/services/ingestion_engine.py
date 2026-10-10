import os
import uuid
import threading
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from .manifest_service import ManifestService
from .youtube_service import YouTubeService
from .transcription_service import TranscriptionService
from .chunking_service import ChunkingService
from .embedding_service import EmbeddingService
from .qdrant_service import QdrantService
from ..models.manifest import VideoStage
from ..models.schema import IngestJobResponse, VideoJobSummary
from ..config import TRANSCRIPT_DIR, CHUNK_DIR, AUDIO_DIR
from ..utils.logger import logger

class IngestionEngine:
    _instance = None
    _lock = threading.RLock()

    def __init__(self):
        self.manifest_service = ManifestService.get_instance()
        self.embedding_service = EmbeddingService.get_instance()
        self.qdrant_service = QdrantService.get_instance()
        
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.active_job_lock = threading.RLock()
        self._is_running = False

    @classmethod
    def get_instance(cls) -> "IngestionEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = IngestionEngine()
            return cls._instance

    def create_job(self, url: str, force_reprocess: bool = False) -> str:
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "url": url,
            "force_reprocess": force_reprocess,
            "is_playlist": False,
            "playlist_id": None,
            "playlist_title": None,
            "status": "pending",
            "total_videos": 0,
            "completed_videos": 0,
            "skipped_videos": 0,
            "failed_videos": 0,
            "current_stage": "initialized",
            "current_video_id": None,
            "current_video_title": None,
            "error": None,
            "message": "Job queued for processing",
            "videos": [],
            "created_at": datetime.utcnow().isoformat(),
        }

        # Start in background thread
        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, url, force_reprocess),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job_status(self, job_id: str) -> Optional[IngestJobResponse]:
        job_data = self.jobs.get(job_id)
        if not job_data:
            return None
        return IngestJobResponse(**job_data)

    def _run_job(self, job_id: str, url: str, force_reprocess: bool):
        job = self.jobs[job_id]
        job["status"] = "running"
        job["current_stage"] = "discovering"
        logger.info(f"Starting ingestion job {job_id} for URL: {url}")

        try:
            discovery_result = YouTubeService.discover(url)
            is_playlist = discovery_result["is_playlist"]
            playlist_id = discovery_result["playlist_id"]
            playlist_title = discovery_result["playlist_title"]
            videos = discovery_result["videos"]

            job["is_playlist"] = is_playlist
            job["playlist_id"] = playlist_id
            job["playlist_title"] = playlist_title
            job["total_videos"] = len(videos)

            if is_playlist and playlist_id:
                video_ids = [v["video_id"] for v in videos]
                self.manifest_service.register_playlist(
                    playlist_id=playlist_id,
                    title=playlist_title or "YouTube Playlist",
                    url=url,
                    video_ids=video_ids,
                )

            # Register each video in manifest
            for v in videos:
                self.manifest_service.register_video(
                    video_id=v["video_id"],
                    title=v["title"],
                    original_url=v["url"],
                    duration=v["duration"],
                    playlist_id=playlist_id,
                    playlist_title=playlist_title,
                )
                job["videos"].append(
                    VideoJobSummary(
                        video_id=v["video_id"],
                        title=v["title"],
                        duration=v["duration"],
                        status="pending",
                        stage="discovered",
                    ).model_dump()
                )

            # Process videos sequentially to manage memory & CPU on M2
            for idx, v in enumerate(videos):
                v_id = v["video_id"]
                v_title = v["title"]
                job["current_video_id"] = v_id
                job["current_video_title"] = v_title

                # Check if already completed and not force
                if not force_reprocess and self.manifest_service.is_video_completed(v_id):
                    logger.info(f"Skipping already completed video: {v_id} ({v_title})")
                    job["skipped_videos"] += 1
                    job["videos"][idx]["status"] = "skipped"
                    job["videos"][idx]["stage"] = "already_indexed"
                    continue

                # Process single video through stages
                try:
                    self._process_single_video(
                        video_dict=v,
                        playlist_id=playlist_id,
                        job=job,
                        video_idx=idx,
                    )
                    job["completed_videos"] += 1
                    job["videos"][idx]["status"] = "completed"
                    job["videos"][idx]["stage"] = "fully_completed"
                except Exception as e:
                    logger.error(f"Error processing video {v_id}: {e}")
                    job["failed_videos"] += 1
                    job["videos"][idx]["status"] = "failed"
                    job["videos"][idx]["stage"] = "failed"
                    job["videos"][idx]["error"] = str(e)
                    self.manifest_service.update_video_stage(
                        video_id=v_id,
                        stage=VideoStage.FAILED,
                        status="failed",
                        error=str(e),
                    )

            # Job finished
            job["status"] = "completed" if job["failed_videos"] == 0 else "partially_completed"
            job["current_stage"] = "completed"
            job["current_video_id"] = None
            job["current_video_title"] = None
            job["message"] = (
                f"Ingestion finished. Total: {job['total_videos']}, "
                f"Completed: {job['completed_videos']}, "
                f"Skipped: {job['skipped_videos']}, "
                f"Failed: {job['failed_videos']}."
            )
            logger.info(f"Job {job_id} finished: {job['message']}")

        except Exception as e:
            logger.error(f"Job {job_id} failed catastrophically: {e}")
            job["status"] = "failed"
            job["current_stage"] = "failed"
            job["error"] = str(e)
            job["message"] = f"Job failed: {str(e)}"

    def _process_single_video(
        self,
        video_dict: Dict[str, Any],
        playlist_id: Optional[str],
        job: Dict[str, Any],
        video_idx: int,
    ):
        v_id = video_dict["video_id"]
        v_title = video_dict["title"]

        # Stage 1: Download Audio
        job["current_stage"] = "downloading_audio"
        job["videos"][video_idx]["stage"] = "downloading_audio"
        audio_path = YouTubeService.download_audio(v_id)
        self.manifest_service.update_video_stage(
            video_id=v_id,
            stage=VideoStage.AUDIO_DOWNLOADED,
            audio_path=audio_path,
        )

        # Stage 2: Transcribe Audio
        job["current_stage"] = "transcribing (0%)"
        job["videos"][video_idx]["stage"] = "transcribing"

        def on_transcribe_progress(stage_text: str):
            job["current_stage"] = stage_text
            job["videos"][video_idx]["stage"] = stage_text

        transcript = TranscriptionService.transcribe(
            audio_path=audio_path,
            video_id=v_id,
            title=v_title,
            progress_callback=on_transcribe_progress,
        )
        self.manifest_service.update_video_stage(
            video_id=v_id,
            stage=VideoStage.TRANSCRIPTION_COMPLETED,
            transcript_path=str(TRANSCRIPT_DIR / f"{v_id}.json"),
            duration=transcript.duration,
            language=transcript.language,
            whisper_model=transcript.model,
        )

        # Stage 3: Time-aware Chunking (~75s target)
        job["current_stage"] = "chunking"
        job["videos"][video_idx]["stage"] = "chunking"
        chunks = ChunkingService.chunk_transcript(
            transcript=transcript,
            playlist_id=playlist_id,
        )
        chunk_file_path = ChunkingService.save_chunks(v_id, chunks)
        self.manifest_service.update_video_stage(
            video_id=v_id,
            stage=VideoStage.CHUNKING_COMPLETED,
            chunk_path=chunk_file_path,
            chunk_count=len(chunks),
        )

        # Stage 4: Embed Chunks
        job["current_stage"] = "generating_embeddings"
        job["videos"][video_idx]["stage"] = "generating_embeddings"
        chunk_texts = [c.text for c in chunks]
        embeddings = self.embedding_service.embed_texts(chunk_texts)
        self.manifest_service.update_video_stage(
            video_id=v_id,
            stage=VideoStage.EMBEDDINGS_GENERATED,
        )

        # Stage 5: Upload to Qdrant (Safe replacement per video)
        job["current_stage"] = "indexing_vectors"
        job["videos"][video_idx]["stage"] = "indexing_vectors"
        self.qdrant_service.delete_video_points(v_id)
        self.qdrant_service.upload_chunks(chunks, embeddings)
        self.manifest_service.update_video_stage(
            video_id=v_id,
            stage=VideoStage.FULLY_COMPLETED,
            status="completed",
        )
