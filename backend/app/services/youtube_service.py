import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import yt_dlp
from ..config import AUDIO_DIR
from ..utils.logger import logger

class YouTubeService:
    @staticmethod
    def is_playlist_url(url: str) -> bool:
        return "list=" in url

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        match = re.search(r"list=([a-zA-Z0-9_-]+)", url)
        return match.group(1) if match else None

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        # Handle standard watch?v=, youtu.be/, shorts/, or pure 11-char ID
        if len(url) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", url):
            return url
        v_match = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})", url)
        return v_match.group(1) if v_match else None

    @classmethod
    def discover(cls, url: str) -> Dict[str, Any]:
        """Discovers videos from a single video URL or playlist URL without downloading."""
        options = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                logger.error(f"yt-dlp extraction failed for {url}: {e}")
                raise ValueError(f"Could not retrieve YouTube information for URL: {url}. Details: {str(e)}")

        if info is None:
            raise ValueError(f"No video metadata found for {url}")

        is_playlist = "entries" in info and bool(info.get("entries"))

        if is_playlist:
            playlist_id = info.get("id") or cls.extract_playlist_id(url) or "playlist"
            playlist_title = info.get("title") or "YouTube Playlist"
            entries = info.get("entries", [])
            videos = []
            for entry in entries:
                if entry and isinstance(entry, dict):
                    v_id = entry.get("id")
                    if v_id:
                        videos.append({
                            "video_id": v_id,
                            "title": entry.get("title") or f"Video {v_id}",
                            "duration": float(entry.get("duration") or 0.0),
                            "url": entry.get("url") or f"https://www.youtube.com/watch?v={v_id}",
                        })
            return {
                "is_playlist": True,
                "playlist_id": playlist_id,
                "playlist_title": playlist_title,
                "videos": videos,
            }
        else:
            v_id = info.get("id") or cls.extract_video_id(url)
            if not v_id:
                raise ValueError(f"Could not extract video ID from {url}")
            return {
                "is_playlist": False,
                "playlist_id": None,
                "playlist_title": None,
                "videos": [{
                    "video_id": v_id,
                    "title": info.get("title") or f"Video {v_id}",
                    "duration": float(info.get("duration") or 0.0),
                    "url": f"https://www.youtube.com/watch?v={v_id}",
                }],
            }

    @classmethod
    def download_audio(cls, video_id: str, audio_dir: Path = AUDIO_DIR) -> str:
        """Downloads audio-only for a given video ID using yt-dlp and FFmpeg."""
        audio_dir.mkdir(parents=True, exist_ok=True)
        target_path = audio_dir / f"{video_id}.mp3"

        # Check if already downloaded and valid (> 10KB)
        if target_path.exists() and target_path.stat().st_size > 10240:
            logger.info(f"Audio for {video_id} already exists at {target_path}")
            return str(target_path)

        output_tmpl = str(audio_dir / f"{video_id}.%(ext)s")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_tmpl,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
        }

        logger.info(f"Downloading audio for video {video_id}...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as e:
            logger.error(f"Failed to download audio for {video_id}: {e}")
            raise RuntimeError(f"Audio download failed for video {video_id}: {str(e)}")

        if not target_path.exists() or target_path.stat().st_size == 0:
            raise RuntimeError(f"Audio file {target_path} was not created or is empty.")

        logger.info(f"Audio downloaded successfully for {video_id}: {target_path}")
        return str(target_path)
