import numpy as np
from typing import List, Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model 'BAAI/bge-small-en-v1.5'...")
            self._model = SentenceTransformer('BAAI/bge-small-en-v1.5')
            logger.info("Embedding model loaded successfully (384 dimensions)")
        return self._model

    def encode(self, text: str) -> Optional[List[float]]:
        try:
            model = self._load_model()
            embedding = model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            return None

    def is_available(self) -> bool:
        try:
            self._load_model()
            return True
        except Exception:
            return False


embedding_service = EmbeddingService()
