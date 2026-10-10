from fastapi import APIRouter, HTTPException
from typing import List
from ..models.schema import PlaylistSummary, IngestJobResponse
from ..services.manifest_service import ManifestService
from ..services.ingestion_engine import IngestionEngine

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])

@router.get("", response_model=List[PlaylistSummary])
def list_playlists():
    manifest_service = ManifestService.get_instance()
    playlists = manifest_service.list_playlists()
    
    summaries = []
    for pl in playlists:
        total = len(pl.video_ids)
        indexed = 0
        for vid in pl.video_ids:
            if manifest_service.is_video_completed(vid):
                indexed += 1
        summaries.append(
            PlaylistSummary(
                playlist_id=pl.playlist_id,
                title=pl.title,
                url=pl.url,
                total_videos=total,
                indexed_videos=indexed,
                last_synced_at=pl.last_synced_at,
            )
        )
    return summaries

@router.post("/{playlist_id}/sync", response_model=IngestJobResponse)
def sync_playlist(playlist_id: str):
    manifest_service = ManifestService.get_instance()
    playlist = manifest_service.get_playlist(playlist_id)
    if not playlist:
        raise HTTPException(
            status_code=404,
            detail=f"Playlist '{playlist_id}' not found in registered playlists. Please ingest its URL first."
        )
    
    engine = IngestionEngine.get_instance()
    job_id = engine.create_job(url=playlist.url, force_reprocess=False)
    job_status = engine.get_job_status(job_id)
    return job_status
