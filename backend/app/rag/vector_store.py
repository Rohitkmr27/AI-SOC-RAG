"""Qdrant storage adapter supporting local and Qdrant Cloud deployments."""

import os
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.rag.config import DEFAULT_COLLECTION_NAME, DEFAULT_VECTOR_STORE_DIRECTORY
from app.rag.schemas import DocumentChunk


class QdrantStore:
    """Adapter around Qdrant supporting local persistence and Qdrant Cloud."""

    def __init__(
        self,
        path: Path = DEFAULT_VECTOR_STORE_DIRECTORY,
        collection_name: str = DEFAULT_COLLECTION_NAME,
    ) -> None:
        self.path = Path(path)
        self.collection_name = collection_name

        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        try:
            from qdrant_client import QdrantClient
        except ImportError as error:
            raise RuntimeError(
                "qdrant-client is required for vector storage. "
                "Install backend/requirements.txt first."
            ) from error

        if qdrant_url:
            # Cloud deployment
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
            )
        else:
            # Local development
            self.path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(self.path))

    def recreate_collection(self, vector_size: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    def upsert(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> None:
        from qdrant_client.models import PointStruct

        if len(chunks) != len(vectors):
            raise ValueError("Each chunk must have exactly one embedding.")

        points = [
            PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector=vector,
                payload={
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "file_name": chunk.file_name,
                    "file_type": chunk.file_type,
                    "content": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "metadata": chunk.metadata,
                    "title": chunk.metadata.get("title"),
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

    def search(
        self,
        vector: list[float],
        top_k: int,
        score_threshold: float | None = None,
    ) -> list[Any]:
        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        return self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        ).points