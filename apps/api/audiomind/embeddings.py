from __future__ import annotations

import hashlib
import logging
import math
import re


logger = logging.getLogger(__name__)


class EmbeddingService:
    """Semantic embeddings with a dependency-free fallback for offline operation."""

    def __init__(self, model_name: str, fallback_dimensions: int = 384):
        self.model_name = model_name
        self.fallback_dimensions = fallback_dimensions
        self._model = None
        self._semantic_unavailable = False

    @property
    def method(self) -> str:
        return "sentence-transformers" if self._model is not None else "hashing-fallback"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        if model is not None:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return [vector.tolist() for vector in vectors]
        return [self._hash_embedding(text) for text in texts]

    def _load_model(self):
        if self._model is not None or self._semantic_unavailable:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        except Exception as exc:
            self._semantic_unavailable = True
            logger.warning("Semantic embedding model unavailable; using hashing fallback: %s", exc)
        return self._model

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.fallback_dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.fallback_dimensions
            vector[index] += -1.0 if value & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
