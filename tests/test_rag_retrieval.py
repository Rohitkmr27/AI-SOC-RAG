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


def test_similarity_search_rejects_invalid_query(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        search_chunks("", db_path=tmp_path / "missing_fts.db")


def test_fts_missing_database_handled_gracefully(tmp_path: Path) -> None:
    results = search_chunks("DDoS attack mitigation", db_path=tmp_path / "nonexistent.db")
    assert results == []


def test_fts_index_builder_and_retrieval(tmp_path: Path) -> None:
    chunks_path = tmp_path / "chunks.jsonl"
    chunk = make_chunk(text="DDoS TCP SYN flood mitigation guidance")
    chunks_path.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")

    db_path = tmp_path / "knowledge_fts.db"
    from scripts.build_knowledge_index import build_fts_index

    read, indexed, skipped, size_mb = build_fts_index(chunks_path, db_path)
    assert (read, indexed, skipped) == (1, 1, 0)
    assert db_path.exists()

    results = search_chunks("DDoS SYN flood", top_k=5, db_path=db_path)
    assert len(results) == 1
    assert results[0]["chunk_id"] == chunk.chunk_id
    assert results[0]["content"] == "DDoS TCP SYN flood mitigation guidance"
    assert results[0]["title"] == "Security Guide"
    assert results[0]["score"] > 0.0


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