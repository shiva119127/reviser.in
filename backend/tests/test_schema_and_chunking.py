import pytest
from backend.app.models.schema import TranscriptData, TranscriptSegment, ChunkData
from backend.app.services.chunking_service import ChunkingService
from backend.app.services.youtube_service import YouTubeService

def test_youtube_id_extraction():
    url1 = "https://www.youtube.com/watch?v=ahaLgJr3HcU"
    url2 = "https://youtu.be/ahaLgJr3HcU?t=10"
    url3 = "https://www.youtube.com/playlist?list=PLW4OpyGE0RdY"
    
    assert YouTubeService.extract_video_id(url1) == "ahaLgJr3HcU"
    assert YouTubeService.extract_video_id(url2) == "ahaLgJr3HcU"
    assert YouTubeService.extract_playlist_id(url3) == "PLW4OpyGE0RdY"
    assert YouTubeService.is_playlist_url(url3) is True
    assert YouTubeService.is_playlist_url(url1) is False

def test_time_aware_chunking():
    # Construct a synthetic 180s transcript
    segments = [
        TranscriptSegment(start=0.0, end=25.0, text="First lecture intro segment."),
        TranscriptSegment(start=25.0, end=50.0, text="Second segment explaining binary search."),
        TranscriptSegment(start=50.0, end=75.0, text="Third segment concluding the search concept."),
        TranscriptSegment(start=75.0, end=110.0, text="Fourth segment starting time complexity analysis."),
        TranscriptSegment(start=110.0, end=150.0, text="Fifth segment explaining O(log n)."),
        TranscriptSegment(start=150.0, end=180.0, text="Final segment wrapping up the lecture."),
    ]
    transcript = TranscriptData(
        video_id="test_video_123",
        title="Binary Search Lecture",
        language="en",
        model="small",
        duration=180.0,
        segments=segments,
    )

    chunks = ChunkingService.chunk_transcript(transcript, playlist_id="PL_TEST", target_duration=75.0)

    assert len(chunks) >= 2
    # Check first chunk
    c0 = chunks[0]
    assert c0.video_id == "test_video_123"
    assert c0.playlist_id == "PL_TEST"
    assert c0.start == 0.0
    assert c0.end >= 75.0
    assert "First lecture intro" in c0.text
    assert c0.timestamped_url == "https://www.youtube.com/watch?v=test_video_123&t=0s"
    assert c0.chunk_id.startswith("test_video_123_c0_")

    # Check second chunk
    c1 = chunks[1]
    assert c1.start >= 75.0
    assert c1.chunk_id.startswith("test_video_123_c1_")
    assert c1.timestamped_url.startswith("https://www.youtube.com/watch?v=test_video_123&t=")

def test_chunk_identity_stability():
    transcript = TranscriptData(
        video_id="vid_abc",
        title="Test Title",
        language="en",
        model="small",
        duration=100.0,
        segments=[
            TranscriptSegment(start=0.0, end=40.0, text="Segment one."),
            TranscriptSegment(start=40.0, end=80.0, text="Segment two."),
        ],
    )
    chunks_run1 = ChunkingService.chunk_transcript(transcript)
    chunks_run2 = ChunkingService.chunk_transcript(transcript)

    assert len(chunks_run1) == len(chunks_run2)
    for c1, c2 in zip(chunks_run1, chunks_run2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.start == c2.start
        assert c1.end == c2.end
        assert c1.text == c2.text
