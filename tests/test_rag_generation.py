"""Tests for Stage 5 RAG answer generation, prompt construction, and API."""

import io
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.main import app
from app.rag.api import get_llm_provider
from app.rag.config import DEFAULT_RAG_MAX_CONTEXT_CHARS
from app.rag.generate import main as cli_main
from app.rag.generator import (
    FALLBACK_EMPTY_ANSWER,
    SYSTEM_PROMPT,
    build_sources_list,
    build_user_prompt,
    construct_context,
    generate_rag_answer,
)
from app.rag.llm import GeminiProvider, LLMProvider
from app.rag.schemas import RAGRequest, RAGResponse, RAGSource


class MockLLM(LLMProvider):
    """Mock LLM provider that records prompts and returns pre-configured text."""

    def __init__(self, response_text: str = "A brute force attack systematically guesses passwords.") -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "system_instruction": system_instruction})
        return self.response_text


def make_test_chunk(
    chunk_id: str = "chunk1",
    score: float = 0.85,
    content: str = "Brute force consists of systematically guessing credentials.",
    title: str = "Brute Force Technique",
) -> dict[str, Any]:
    return {
        "score": score,
        "document_id": "doc12345",
        "chunk_id": chunk_id,
        "source": "mitre/parsed/t1110.md",
        "file_name": "t1110.md",
        "file_type": "md",
        "content": content,
        "chunk_index": 0,
        "title": title,
        "metadata": {"relative_path": "mitre/parsed/t1110.md"},
    }


# ==========================================
# 1. Request Validation Tests
# ==========================================

def test_rag_request_validation_valid() -> None:
    req = RAGRequest(query="  What is brute force?  ", top_k=3, score_threshold=0.5)
    assert req.query == "What is brute force?"
    assert req.top_k == 3
    assert req.score_threshold == 0.5


def test_rag_request_validation_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        RAGRequest(query="")

    with pytest.raises(ValidationError):
        RAGRequest(query="   ")


def test_rag_request_validation_rejects_invalid_top_k() -> None:
    with pytest.raises(ValidationError):
        RAGRequest(query="Valid query", top_k=0)

    with pytest.raises(ValidationError):
        RAGRequest(query="Valid query", top_k=25)


def test_rag_request_validation_rejects_invalid_score_threshold() -> None:
    with pytest.raises(ValidationError):
        RAGRequest(query="Valid query", score_threshold=-0.1)

    with pytest.raises(ValidationError):
        RAGRequest(query="Valid query", score_threshold=1.5)


# ==========================================
# 2. Context Construction Tests
# ==========================================

def test_context_construction_formats_metadata_and_content() -> None:
    chunks = [
        make_test_chunk(chunk_id="c1", score=0.9, content="First chunk content.", title="Doc One"),
        make_test_chunk(chunk_id="c2", score=0.8, content="Second chunk content.", title="Doc Two"),
    ]
    context_str, used_chunks = construct_context(chunks, max_chars=1000)

    assert len(used_chunks) == 2
    assert "--- [Document 1] Source: mitre/parsed/t1110.md" in context_str
    assert "Title: Doc One | Chunk ID: c1" in context_str
    assert "First chunk content." in context_str
    assert "--- [Document 2] Source: mitre/parsed/t1110.md" in context_str
    assert "Second chunk content." in context_str


def test_context_construction_respects_max_chars() -> None:
    chunks = [
        make_test_chunk(chunk_id="c1", content="A" * 100),
        make_test_chunk(chunk_id="c2", content="B" * 100),
        make_test_chunk(chunk_id="c3", content="C" * 100),
    ]
    context_str, used_chunks = construct_context(chunks, max_chars=250)

    assert len(context_str) <= 250
    assert len(used_chunks) < 3


# ==========================================
# 3. Prompt Construction & Grounding Tests
# ==========================================

def test_prompt_construction_contains_context_and_grounding_rules() -> None:
    context = "Document content about password spraying."
    query = "What is password spraying?"
    prompt = build_user_prompt(query, context)

    assert "Context from Security Knowledge Base:" in prompt
    assert context in prompt
    assert f"Question: {query}" in prompt
    assert "Instructions: Answer the question using ONLY the security context" in prompt
    assert "Do not invent facts or sources." in prompt


def test_system_prompt_enforces_anti_hallucination_rules() -> None:
    assert "cybersecurity assistant for an AI-SOC system" in SYSTEM_PROMPT
    assert "Answer using only the supplied retrieved security knowledge." in SYSTEM_PROMPT
    assert "Do not invent facts or sources." in SYSTEM_PROMPT
    assert "explicitly say that the available knowledge base does not provide enough information" in SYSTEM_PROMPT
    assert "Do not claim that an event occurred unless supported by the supplied context." in SYSTEM_PROMPT


# ==========================================
# 4. Source Metadata Preservation Tests
# ==========================================

def test_source_metadata_preservation() -> None:
    raw_chunks = [
        make_test_chunk(chunk_id="abc12345", score=0.78, title="Attack Pattern T1110"),
    ]
    sources = build_sources_list(raw_chunks)

    assert len(sources) == 1
    src = sources[0]
    assert isinstance(src, RAGSource)
    assert src.source == "mitre/parsed/t1110.md"
    assert src.file_name == "t1110.md"
    assert src.document_id == "doc12345"
    assert src.chunk_id == "abc12345"
    assert src.chunk_index == 0
    assert src.score == pytest.approx(0.78)
    assert src.title == "Attack Pattern T1110"


# ==========================================
# 5. Empty Retrieval & Guard Behavior Tests
# ==========================================

def test_empty_retrieval_returns_fallback_without_calling_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: [])
    mock_llm = MockLLM()

    response = generate_rag_answer("Unknown exotic threat?", llm_client=mock_llm)

    assert response.answer == FALLBACK_EMPTY_ANSWER
    assert response.sources == []
    assert len(mock_llm.calls) == 0, "LLM must NOT be called when retrieval is empty"


def test_score_threshold_filtering_can_trigger_empty_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulating search_chunks returning empty when score_threshold is not met
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: [])
    mock_llm = MockLLM()

    response = generate_rag_answer(
        "Low relevance query",
        score_threshold=0.95,
        llm_client=mock_llm,
    )

    assert response.answer == FALLBACK_EMPTY_ANSWER
    assert response.sources == []
    assert len(mock_llm.calls) == 0


# ==========================================
# 6. Missing API Key / Configuration Tests
# ==========================================

def test_missing_gemini_api_key_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider(api_key=None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY environment variable is not set"):
        provider.generate("prompt text")


def test_gemini_provider_does_not_fail_on_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider()
    assert provider.api_key is None or provider.api_key == ""


# ==========================================
# 7. Successful Generation with Mocked LLM
# ==========================================

def test_successful_generation_with_mocked_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunks = [
        make_test_chunk(chunk_id="chunk_a", score=0.88, content="Brute force attempts every combination."),
    ]
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: test_chunks)

    expected_answer = "Based on the retrieved context, brute force attempts every combination."
    mock_llm = MockLLM(response_text=expected_answer)

    response = generate_rag_answer("What is brute force?", llm_client=mock_llm)

    assert response.answer == expected_answer
    assert len(response.sources) == 1
    assert response.sources[0].chunk_id == "chunk_a"
    assert response.sources[0].score == pytest.approx(0.88)

    # Verify LLM call received strict system instruction and user prompt
    assert len(mock_llm.calls) == 1
    call = mock_llm.calls[0]
    assert call["system_instruction"] == SYSTEM_PROMPT
    assert "What is brute force?" in call["prompt"]
    assert "Brute force attempts every combination." in call["prompt"]


# ==========================================
# 8. FastAPI Endpoint Tests
# ==========================================

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole

mock_analyst = User(
    username="test_analyst",
    role=UserRole.ANALYST,
    is_active=True,
)


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: mock_analyst
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_rag_api_endpoint_success(monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunks = [make_test_chunk(chunk_id="c_api", score=0.91)]
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: test_chunks)

    mock_llm = MockLLM(response_text="Grounded answer from API.")
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm

    try:
        client = TestClient(app)
        res = client.post("/rag/query", json={"query": "What is brute force?", "top_k": 2})

        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == "Grounded answer from API."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["chunk_id"] == "c_api"
        assert data["sources"][0]["score"] == pytest.approx(0.91)
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_rag_api_endpoint_empty_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: [])
    mock_llm = MockLLM()
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm

    try:
        client = TestClient(app)
        res = client.post("/rag/query", json={"query": "Completely unknown subject"})

        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == FALLBACK_EMPTY_ANSWER
        assert data["sources"] == []
        assert len(mock_llm.calls) == 0
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_rag_api_endpoint_validation_error() -> None:
    client = TestClient(app)
    res = client.post("/rag/query", json={"query": ""})
    assert res.status_code == 422

    res2 = client.post("/rag/query", json={"query": "Valid", "top_k": -1})
    assert res2.status_code == 422


def test_rag_api_endpoint_missing_api_key_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    test_chunks = [make_test_chunk()]
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: test_chunks)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Use the real GeminiProvider without API key
    client = TestClient(app)
    res = client.post("/rag/query", json={"query": "What is brute force?"})

    assert res.status_code == 503
    assert "GEMINI_API_KEY" in res.json()["detail"]



# ==========================================
# 9. CLI Tests
# ==========================================

def test_cli_generation_with_mocked_search_and_llm(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    test_chunks = [make_test_chunk(chunk_id="cli_chunk", score=0.82)]
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: test_chunks)
    monkeypatch.setattr("app.rag.generate.GeminiProvider", lambda **kwargs: MockLLM("CLI grounded response."))

    exit_code = cli_main(["What is brute force?", "--top-k", "2"])

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "CLI grounded response." in captured
    assert "cli_chunk" in captured
    assert "Score: 0.8200" in captured


def test_cli_generation_json_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    test_chunks = [make_test_chunk(chunk_id="cli_chunk_json", score=0.85)]
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: test_chunks)
    monkeypatch.setattr("app.rag.generate.GeminiProvider", lambda **kwargs: MockLLM("JSON response."))

    exit_code = cli_main(["What is brute force?", "--json"])

    assert exit_code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["answer"] == "JSON response."
    assert data["sources"][0]["chunk_id"] == "cli_chunk_json"


def test_cli_missing_api_key_reports_clean_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    test_chunks = [make_test_chunk()]
    monkeypatch.setattr("app.rag.generator.search_chunks", lambda **kwargs: test_chunks)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    exit_code = cli_main(["What is brute force?"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "Generation error:" in err
    assert "GEMINI_API_KEY" in err
