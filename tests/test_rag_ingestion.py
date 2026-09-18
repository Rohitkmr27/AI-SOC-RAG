"""Temporary-file tests for Stage 4 knowledge-base ingestion."""

import sys
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.rag.chunking import chunk_document
from app.rag.document_loader import load_documents, write_chunks
from app.rag.schemas import KnowledgeDocument


def create_text_pdf(path: Path) -> None:
    """Create a small, real PDF containing extractable text for loader testing."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (PDF security guidance) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as stream:
        writer.write(stream)


def test_loads_txt_markdown_and_pdf_with_metadata(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("Network security note", encoding="utf-8")
    nested = tmp_path / "guides"
    nested.mkdir()
    (nested / "guide.md").write_text("# Incident guide", encoding="utf-8")
    create_text_pdf(tmp_path / "reference.pdf")

    result = load_documents(tmp_path)

    assert len(result.documents) == 3
    assert not result.errors
    assert {document.file_type for document in result.documents} == {"txt", "md", "pdf"}
    assert next(document for document in result.documents if document.file_type == "pdf").text == "PDF security guidance"
    assert next(document for document in result.documents if document.file_name == "guide.md").source == "guides/guide.md"


def test_handles_unsupported_and_empty_documents(tmp_path: Path) -> None:
    (tmp_path / "unsupported.docx").write_text("not processed", encoding="utf-8")
    (tmp_path / "empty.txt").write_text("   ", encoding="utf-8")

    result = load_documents(tmp_path)

    assert not result.documents
    assert len(result.errors) == 2


def test_document_ids_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "same.txt").write_text("Repeatable source", encoding="utf-8")
    first = load_documents(tmp_path).documents[0]
    second = load_documents(tmp_path).documents[0]
    assert first.document_id == second.document_id


def test_chunking_preserves_metadata_and_word_overlap() -> None:
    document = KnowledgeDocument(
        document_id="a" * 64,
        source="notes/example.txt",
        file_name="example.txt",
        file_type="txt",
        text="alpha bravo charlie delta echo foxtrot golf hotel",
        metadata={"relative_path": "notes/example.txt"},
    )
    chunks = chunk_document(document, chunk_size=24, chunk_overlap=12)

    assert len(chunks) > 1
    assert chunks[0].document_id == document.document_id
    assert chunks[0].metadata == document.metadata
    assert "charlie" in chunks[0].text and "charlie" in chunks[1].text
    assert chunks[0].chunk_id != chunks[1].chunk_id


def test_write_chunks_outputs_jsonl(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "document.txt").write_text("A short legitimate document.", encoding="utf-8")
    output = tmp_path / "processed" / "chunks.jsonl"
    documents, errors = write_chunks(raw, output, chunk_size=100, chunk_overlap=10)

    assert (documents, errors) == (1, 0)
    assert output.read_text(encoding="utf-8").count("chunk_id") == 1
