import os
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from faster_whisper import WhisperModel
from ..config import (
    WHISPER_MODEL,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
    TRANSCRIPT_DIR,
)
from ..models.schema import TranscriptData, TranscriptSegment
from ..utils.logger import logger

class TranscriptionService:
    _model_instance = None
    _model_lock = threading.RLock()

    @classmethod
    def get_model(cls) -> WhisperModel:
        with cls._model_lock:
            if cls._model_instance is None:
                logger.info(
                    f"Loading faster-whisper model '{WHISPER_MODEL}' on device='{WHISPER_DEVICE}', compute_type='{WHISPER_COMPUTE_TYPE}'..."
                )
                cls._model_instance = WhisperModel(
                    WHISPER_MODEL,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                    cpu_threads=4,
                )
                logger.info("faster-whisper model loaded successfully.")
            return cls._model_instance

    @classmethod
    def is_transcript_valid(cls, transcript_path: Path) -> bool:
        if not transcript_path.exists():
            return False
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                TranscriptData.model_validate(data)
                return len(data.get("segments", [])) > 0
        except Exception:
            return False

    @classmethod
    def transcribe(
        cls,
        audio_path: str,
        video_id: str,
        title: str,
        language: Optional[str] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> TranscriptData:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = TRANSCRIPT_DIR / f"{video_id}.json"

        # Check existing transcript
        if not force and cls.is_transcript_valid(output_path):
            logger.info(f"Valid transcript already exists for {video_id}: {output_path}")
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return TranscriptData.model_validate(data)

        model = cls.get_model()
        logger.info(f"Transcribing audio for {video_id} ({title})...")

        try:
            # Using beam_size=1 and best_of=1 for 5x-8x faster CPU inference on M2
            segments_gen, info = model.transcribe(
                audio_path,
                language=language,  # None means auto-detect
                task="transcribe",
                beam_size=1,
                best_of=1,
                vad_filter=True,
                temperature=0.0,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                no_speech_threshold=0.6,
            )

            total_audio_duration = float(info.duration) if hasattr(info, "duration") and info.duration else 0.0

            segments_list = []
            duration = 0.0

            for seg in segments_gen:
                text = seg.text.strip()
                if not text:
                    continue
                start = round(float(seg.start), 2)
                end = round(float(seg.end), 2)
                segments_list.append(TranscriptSegment(start=start, end=end, text=text))
                duration = max(duration, end)

                if progress_callback and total_audio_duration > 0:
                    percent = min(99, int((end / total_audio_duration) * 100))
                    mins_done = int(end // 60)
                    secs_done = int(end % 60)
                    mins_tot = int(total_audio_duration // 60)
                    secs_tot = int(total_audio_duration % 60)
                    progress_callback(
                        f"transcribing ({percent}% · {mins_done}:{secs_done:02d}/{mins_tot}:{secs_tot:02d})"
                    )

            detected_language = info.language if hasattr(info, "language") else "en"

            transcript_data = TranscriptData(
                video_id=video_id,
                title=title,
                language=detected_language,
                model=WHISPER_MODEL,
                duration=round(duration, 2),
                segments=segments_list,
            )

            # Atomic file save
            temp_path = output_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(transcript_data.model_dump(), f, indent=2, ensure_ascii=False)
            temp_path.replace(output_path)

            logger.info(
                f"Transcription complete for {video_id}: {len(segments_list)} segments, duration={duration:.1f}s, language={detected_language}"
            )
            return transcript_data

        except Exception as e:
            logger.error(f"Transcription failed for {video_id}: {e}")
            raise RuntimeError(f"Transcription failed for video {video_id}: {str(e)}")
