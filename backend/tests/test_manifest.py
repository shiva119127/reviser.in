import pytest
from pathlib import Path
from backend.app.models.manifest import VideoStage, VideoManifestEntry
from backend.app.services.manifest_service import ManifestService

def test_manifest_lifecycle(tmp_path):
    manifest_file = tmp_path / "test_manifest.json"
    service = ManifestService(manifest_path=manifest_file)

    # Register video
    service.register_video(
        video_id="v_101",
        title="Lecture 101",
        original_url="https://www.youtube.com/watch?v=v_101",
        duration=300.0,
        playlist_id="pl_1",
        playlist_title="Course 1",
    )

    entry = service.get_video("v_101")
    assert entry is not None
    assert entry.video_id == "v_101"
    assert entry.status == "discovered"
    assert entry.stage == VideoStage.DISCOVERED
    assert service.is_video_completed("v_101") is False

    # Update through stages
    service.update_video_stage(
        video_id="v_101",
        stage=VideoStage.AUDIO_DOWNLOADED,
        audio_path="/path/to/v_101.mp3",
    )
    assert service.get_video("v_101").stage == VideoStage.AUDIO_DOWNLOADED

    # Update to completion
    dummy_transcript = tmp_path / "v_101.json"
    dummy_transcript.write_text("{}")
    service.update_video_stage(
        video_id="v_101",
        stage=VideoStage.FULLY_COMPLETED,
        status="completed",
        transcript_path=str(dummy_transcript),
        chunk_count=5,
    )
    assert service.get_video("v_101").stage == VideoStage.FULLY_COMPLETED
    assert service.is_video_completed("v_101") is True

    # Register and list playlists
    service.register_playlist(
        playlist_id="pl_1",
        title="Course 1",
        url="https://www.youtube.com/playlist?list=pl_1",
        video_ids=["v_101"],
    )
    playlists = service.list_playlists()
    assert len(playlists) == 1
    assert playlists[0].playlist_id == "pl_1"
