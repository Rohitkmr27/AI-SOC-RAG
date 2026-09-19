"""Focused tests for Stage 4.2 embeddings, indexing, and retrieval."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.rag.embeddings import EmbeddingService
from app.rag.index import index_chunks, read_chunks
from app.rag.schemas import DocumentChunk
from app.rag.search import search_chunks
from app.rag.vector_store import QdrantStore


class FakeVectors(list):
    def tolist(self):
        return list(self)


class FakeModel:
    def eval(self):
        return self

    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts, **kwargs):
        return FakeVectors([[float(len(text)), 1.0, 0.0] for text in texts])


def make_chunk(text: str = "brute force attack guidance") -> DocumentChunk:
    return DocumentChunk(
        chunk_id="a" * 64,
        document_id="b" * 64,
        source="guide.md",
        file_name="guide.md",
        file_type="md",
        text=text,
        chunk_index=0,
        metadata={"title": "Security Guide", "relative_path": "guide.md"},
    )


def test_embedding_generation_dimension_and_repeatability() -> None:
    service = EmbeddingService("local-test-model")
    service._model = FakeModel()

    first = service.embed(["repeatable text"])
    second = service.embed(["repeatable text"])

    assert service.dimension == 3
    assert first == second == [[15.0, 1.0, 0.0]]


def test_embedding_rejects_empty_text() -> None:
    service = EmbeddingService("local-test-model")
    service._model = FakeModel()
    with pytest.raises(ValueError, match="non-empty"):
        service.embed_query("  ")


def test_read_chunks_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        read_chunks(tmp_path / "missing.jsonl")


def test_indexing_preserves_payload_and_reports_dimension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(make_chunk().model_dump_json() + "\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeStore:
        def __init__(self, path, collection_name):
            captured["path"] = path
            captured["collection"] = collection_name

        def recreate_collection(self, vector_size):
            captured["dimension"] = vector_size

        def upsert(self, chunks, vectors):
            captured["chunks"] = chunks
            captured["vectors"] = vectors

    fake_service = EmbeddingService("local-test-model")
    fake_service._model = FakeModel()
    monkeypatch.setattr("app.rag.index.EmbeddingService", lambda model: fake_service)
    monkeypatch.setattr("app.rag.index.QdrantStore", FakeStore)
    count, dimension = index_chunks(chunks_path, tmp_path / "vectors", "test_collection", "local-test-model")

    assert (count, dimension) == (1, 3)
    assert captured["chunks"][0].metadata["title"] == "Security Guide"
    assert captured["vectors"] == [[27.0, 1.0, 0.0]]


def test_similarity_search_returns_scores_and_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeStore:
        def __init__(self, path, collection_name):
            pass

        def search(self, vector, top_k, score_threshold):
            assert vector == [27.0, 1.0, 0.0]
            assert (top_k, score_threshold) == (2, 0.7)
            return [SimpleNamespace(score=0.91, payload={"content": "brute force", "chunk_id": "a" * 64})]

    monkeypatch.setattr("app.rag.search.EmbeddingService", lambda model: EmbeddingService(model))
    monkeypatch.setattr("app.rag.search.QdrantStore", FakeStore)
    service = EmbeddingService("local-test-model")
    service._model = FakeModel()
    monkeypatch.setattr("app.rag.search.EmbeddingService", lambda model: service)

    results = search_chunks("brute force attack guidance", 2, 0.7, tmp_path / "vectors")

    assert results == [{"score": 0.91, "content": "brute force", "chunk_id": "a" * 64}]


def test_similarity_search_rejects_invalid_query(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        search_chunks("", vector_store_path=tmp_path / "vectors")


def test_qdrant_local_store_searches_payload(tmp_path: Path) -> None:
    pytest.importorskip("qdrant_client")
    store = QdrantStore(tmp_path / "vectors", "test_collection")
    store.recreate_collection(3)
    store.upsert([make_chunk()], [[1.0, 0.0, 0.0]])

    points = store.search([1.0, 0.0, 0.0], top_k=1, score_threshold=0.9)

    assert len(points) == 1
    assert points[0].score == pytest.approx(1.0)
    assert points[0].payload["content"] == "brute force attack guidance"
    assert points[0].payload["title"] == "Security Guide"