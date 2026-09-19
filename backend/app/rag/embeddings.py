"""Lazy local embedding service for knowledge-base chunks and queries."""

from typing import Any

from app.rag.config import DEFAULT_EMBEDDING_MODEL


class EmbeddingService:
    """Generate normalized embeddings with a lazily loaded SentenceTransformer."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "sentence-transformers is required for embeddings. Install backend/requirements.txt first."
                ) from error
            self._model = SentenceTransformer(self.model_name, device="cpu")
            self._model.eval()
        return self._model

    @property
    def dimension(self) -> int:
        dimension = self._get_model().get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError("The embedding model did not report a vector dimension.")
        return int(dimension)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("texts must contain only non-empty strings.")
        vectors = self._get_model().encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")
        return self.embed([query])[0]