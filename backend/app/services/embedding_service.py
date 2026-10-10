import threading
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from ..config import EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION
from ..utils.logger import logger

class EmbeddingService:
    _instance = None
    _lock = threading.RLock()

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        logger.info(f"Loading SentenceTransformer model '{model_name}'...")
        self.model = SentenceTransformer(model_name)
        dim = self.model.get_sentence_embedding_dimension()
        if dim != EMBEDDING_DIMENSION:
            logger.warning(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSION}, got {dim}"
            )
        logger.info(f"SentenceTransformer loaded successfully. Embedding dimension: {dim}")

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = EmbeddingService()
            return cls._instance

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        embedding = self.model.encode(
            query,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        if len(embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Generated embedding dimension {len(embedding)} does not match expected {EMBEDDING_DIMENSION}"
            )
        return embedding.tolist()

    def embed_texts(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Embed a batch of text chunks with normalization."""
        if not texts:
            return []
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        
        result = [emb.tolist() for emb in embeddings]
        if result and len(result[0]) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Generated embedding dimension {len(result[0])} does not match expected {EMBEDDING_DIMENSION}"
            )
        return result
