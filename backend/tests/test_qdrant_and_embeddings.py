import pytest
from backend.app.services.qdrant_service import QdrantService
from backend.app.services.embedding_service import EmbeddingService
from backend.app.models.schema import ChunkData

def test_qdrant_point_id_determinism():
    chunk_id = "test_video_c0_0s"
    id1 = QdrantService.generate_point_id(chunk_id)
    id2 = QdrantService.generate_point_id(chunk_id)
    assert id1 == id2
    assert len(id1) == 36  # Standard UUID string length

def test_embedding_dimension():
    service = EmbeddingService.get_instance()
    emb = service.embed_query("What is gradient descent?")
    assert len(emb) == 384
    assert isinstance(emb[0], float)

    batch_emb = service.embed_texts(["Chunk 1 text", "Chunk 2 text"])
    assert len(batch_emb) == 2
    assert len(batch_emb[0]) == 384
    assert len(batch_emb[1]) == 384
