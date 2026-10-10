import uuid
import threading
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from ..config import (
    QDRANT_PATH,
    QDRANT_COLLECTION,
    QDRANT_URL,
    QDRANT_API_KEY,
    EMBEDDING_DIMENSION,
)
from ..models.schema import ChunkData
from ..utils.logger import logger

# Deterministic namespace for point IDs
POINT_NAMESPACE = uuid.UUID("e7b68630-3cb8-4f81-9b16-563d76e4c760")

class QdrantService:
    _instance = None
    _lock = threading.RLock()

    def __init__(
        self,
        path: Optional[str] = None,
        collection_name: str = QDRANT_COLLECTION,
    ):
        self.collection_name = collection_name
        if path is not None:
            if path == ":memory:":
                logger.info("Initializing in-memory Qdrant client...")
                self.client = QdrantClient(":memory:")
            else:
                logger.info(f"Initializing Qdrant client at custom path '{path}'...")
                self.client = QdrantClient(path=path)
            self._ensure_collection()
            return

        # Attempt remote connection only if a valid QDRANT_URL is configured
        if QDRANT_URL:
            try:
                logger.info(f"Connecting to remote Qdrant cluster at '{QDRANT_URL}'...")
                self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=5.0)
                self._ensure_collection()
                logger.info("Connected to remote Qdrant cluster successfully.")
                return
            except Exception as e:
                logger.warning(
                    f"Failed to connect to remote Qdrant cluster at '{QDRANT_URL}' ({e}). "
                    f"Falling back to local embedded storage at '{QDRANT_PATH}'."
                )

        if QDRANT_PATH == ":memory:":
            logger.info("Initializing in-memory Qdrant client...")
            self.client = QdrantClient(":memory:")
        else:
            logger.info(f"Initializing Qdrant client at local path '{QDRANT_PATH}'...")
            self.client = QdrantClient(path=QDRANT_PATH)
        self._ensure_collection()

    @classmethod
    def get_instance(cls) -> "QdrantService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = QdrantService()
            return cls._instance

    def _ensure_collection(self):
        """Ensures the collection exists with cosine distance and correct vector size."""
        try:
            collections = self.client.get_collections()
            names = [c.name for c in collections.collections]
            
            if self.collection_name not in names:
                logger.info(f"Creating Qdrant collection '{self.collection_name}' with dim={EMBEDDING_DIMENSION}, distance=COSINE...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIMENSION,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Collection '{self.collection_name}' created successfully.")
            else:
                info = self.client.get_collection(self.collection_name)
                logger.info(
                    f"Qdrant collection '{self.collection_name}' already exists. Points count: {info.points_count}"
                )
        except Exception as e:
            logger.error(f"Error checking/creating Qdrant collection: {e}")
            raise

    def get_points_count(self) -> int:
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception as e:
            logger.warning(f"Could not get points count: {e}")
            return 0

    @staticmethod
    def generate_point_id(chunk_id: str) -> str:
        """Generates a deterministic UUID string for a chunk ID."""
        return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))

    def delete_video_points(self, video_id: str):
        """Safely deletes all points for a specific video before re-indexing."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id),
                        )
                    ]
                ),
            )
            logger.info(f"Deleted old Qdrant points for video {video_id}")
        except Exception as e:
            logger.warning(f"Could not delete old points for video {video_id}: {e}")

    def upload_chunks(
        self,
        chunks: List[ChunkData],
        embeddings: List[List[float]],
        batch_size: int = 100,
    ) -> int:
        """Uploads chunks with embeddings to Qdrant idempotently."""
        if not chunks or not embeddings:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks count ({len(chunks)}) and embeddings count ({len(embeddings)}) mismatch."
            )

        points = []
        for chunk, emb in zip(chunks, embeddings):
            point_id = self.generate_point_id(chunk.chunk_id)
            payload = chunk.model_dump()
            points.append(
                PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=payload,
                )
            )

        # Upsert in batches
        total_uploaded = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            total_uploaded += len(batch)

        logger.info(
            f"Successfully uploaded {total_uploaded} points to collection '{self.collection_name}'."
        )
        return total_uploaded

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        playlist_id: Optional[str] = None,
        video_id: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Any]:
        """Searches Qdrant for closest transcript chunks."""
        conditions = []
        if playlist_id:
            conditions.append(
                FieldCondition(
                    key="playlist_id",
                    match=MatchValue(value=playlist_id),
                )
            )
        if video_id:
            conditions.append(
                FieldCondition(
                    key="video_id",
                    match=MatchValue(value=video_id),
                )
            )

        query_filter = Filter(must=conditions) if conditions else None

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return response.points
