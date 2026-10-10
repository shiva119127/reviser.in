import re
import json
from pathlib import Path
from typing import List, Optional
from ..config import CHUNK_DIR, TARGET_CHUNK_DURATION
from ..models.schema import TranscriptData, ChunkData
from ..utils.logger import logger

def clean_transcript_segment(text: str) -> str:
    """Removes Whisper repetition artifacts, repeated tokens, and excessive punctuation."""
    if not text:
        return ""
    # Collapse repeating word loops (e.g. "तो तो तो तो" -> "तो", "अगर अगर अगर" -> "अगर")
    cleaned = re.sub(r'(\b[\w\u0900-\u097F]+\b)(?:\s+\1){2,}', r'\1', text)
    # Collapse repeating punctuation or symbols (e.g. "़़़़", ".....", "-----")
    cleaned = re.sub(r'([^\w\s\u0900-\u097F])\1{2,}', r'\1', cleaned)
    # Collapse repeated short phrases
    cleaned = re.sub(r'(.{3,30}?)\1{3,}', r'\1', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

class ChunkingService:
    @staticmethod
    def chunk_transcript(
        transcript: TranscriptData,
        playlist_id: Optional[str] = None,
        target_duration: float = TARGET_CHUNK_DURATION,
    ) -> List[ChunkData]:
        """
        Creates time-aware chunks targeting ~75 seconds of lecture content.
        Preserves chronological ordering, segment start/end times, and sentence boundaries.
        """
        segments = transcript.segments
        if not segments:
            return []

        chunks: List[ChunkData] = []
        current_texts: List[str] = []
        chunk_start: Optional[float] = None
        chunk_end: Optional[float] = None
        chunk_index = 0

        for seg in segments:
            cleaned_seg_text = clean_transcript_segment(seg.text)
            if not cleaned_seg_text:
                continue

            if chunk_start is None:
                chunk_start = seg.start
            
            current_texts.append(cleaned_seg_text)
            chunk_end = seg.end
            current_duration = chunk_end - chunk_start

            # When chunk duration reaches or exceeds target duration (approx 75s),
            # or if current text ends with sentence boundary (. / ? / !), complete chunk.
            text_ends_sentence = cleaned_seg_text.rstrip().endswith((".", "?", "!"))
            if (current_duration >= target_duration) or (current_duration >= target_duration * 0.75 and text_ends_sentence):
                chunk_text = clean_transcript_segment(" ".join(current_texts))
                start_sec = int(chunk_start)
                stable_id = f"{transcript.video_id}_c{chunk_index}_{start_sec}s"
                
                chunk_data = ChunkData(
                    chunk_id=stable_id,
                    video_id=transcript.video_id,
                    title=transcript.title,
                    duration=transcript.duration,
                    start=round(chunk_start, 2),
                    end=round(chunk_end, 2),
                    text=chunk_text,
                    playlist_id=playlist_id,
                    language=transcript.language,
                    youtube_url=f"https://www.youtube.com/watch?v={transcript.video_id}",
                    timestamped_url=f"https://www.youtube.com/watch?v={transcript.video_id}&t={start_sec}s",
                )
                chunks.append(chunk_data)
                
                # Reset for next chunk
                current_texts = []
                chunk_start = None
                chunk_end = None
                chunk_index += 1

        # Handle any remaining segments in final chunk
        if current_texts and chunk_start is not None and chunk_end is not None:
            chunk_text = " ".join(current_texts).strip()
            start_sec = int(chunk_start)
            stable_id = f"{transcript.video_id}_c{chunk_index}_{start_sec}s"
            chunk_data = ChunkData(
                chunk_id=stable_id,
                video_id=transcript.video_id,
                title=transcript.title,
                duration=transcript.duration,
                start=round(chunk_start, 2),
                end=round(chunk_end, 2),
                text=chunk_text,
                playlist_id=playlist_id,
                language=transcript.language,
                youtube_url=f"https://www.youtube.com/watch?v={transcript.video_id}",
                timestamped_url=f"https://www.youtube.com/watch?v={transcript.video_id}&t={start_sec}s",
            )
            chunks.append(chunk_data)

        return chunks

    @classmethod
    def save_chunks(cls, video_id: str, chunks: List[ChunkData], chunk_dir: Path = CHUNK_DIR) -> str:
        """Saves chunks atomically to JSON file."""
        chunk_dir.mkdir(parents=True, exist_ok=True)
        output_path = chunk_dir / f"{video_id}.json"
        temp_path = output_path.with_suffix(".tmp")

        chunks_dict = [chunk.model_dump() for chunk in chunks]
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(chunks_dict, f, indent=2, ensure_ascii=False)
        temp_path.replace(output_path)
        logger.info(f"Saved {len(chunks)} chunks for video {video_id} to {output_path}")
        return str(output_path)

    @classmethod
    def load_chunks(cls, video_id: str, chunk_dir: Path = CHUNK_DIR) -> Optional[List[ChunkData]]:
        """Loads chunks from JSON file."""
        file_path = chunk_dir / f"{video_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [ChunkData.model_validate(item) for item in data]
        except Exception as e:
            logger.error(f"Error loading chunks for {video_id}: {e}")
            return None
