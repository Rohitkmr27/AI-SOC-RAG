"""Offline tests for official knowledge-source bootstrap and MITRE parsing."""

import json
import sys
from pathlib import Path

import pytest

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.rag.mitre_parser import parse_enterprise_attack
from app.rag.source_downloader import OFFICIAL_SOURCES, OfficialSource, download_sources


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.body


def test_official_source_configuration_uses_expected_official_hosts() -> None:
    assert {source.name for source in OFFICIAL_SOURCES} == {
        "MITRE ATT&CK Enterprise",
        "NIST Cybersecurity Framework 2.0",
        "OWASP Top 10:2025",
        "CISA Cross-Sector Cybersecurity Performance Goals",
    }
    assert all(source.url.startswith("https://") for source in OFFICIAL_SOURCES)
    assert "raw.githubusercontent.com/mitre-attack/attack-stix-data" in OFFICIAL_SOURCES[0].url
    assert "nvlpubs.nist.gov" in OFFICIAL_SOURCES[1].url
    assert "owasp.org/Top10/2025" in OFFICIAL_SOURCES[2].url
    assert "cisa.gov" in OFFICIAL_SOURCES[3].url


def test_download_creates_directories_and_manifest_metadata(tmp_path: Path) -> None:
    source = OfficialSource("Test official source", "https://official.example/source.pdf", "cisa/source.pdf", "PDF", "1")
    calls: list[tuple[str, int]] = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse(b"official bytes")

    summary = download_sources(tmp_path / "raw", tmp_path / "manifest.json", sources=(source,), timeout=17, opener=opener)

    assert summary["counts"] == {"downloaded": 1, "skipped": 0, "failed": 0}
    assert (tmp_path / "raw" / "cisa" / "source.pdf").read_bytes() == b"official bytes"
    metadata = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))[source.name]
    assert metadata["official_url"] == source.url
    assert metadata["local_filename"] == "cisa/source.pdf"
    assert metadata["source_type"] == "PDF"
    assert metadata["version"] == "1"
    assert calls == [(source.url, 17)]


def test_existing_source_is_skipped_without_download(tmp_path: Path) -> None:
    source = OfficialSource("Existing source", "https://official.example/source.txt", "nist/source.txt", "TXT")
    target = tmp_path / "raw" / source.relative_path
    target.parent.mkdir(parents=True)
    target.write_text("existing", encoding="utf-8")

    def opener(*args, **kwargs):
        raise AssertionError("skipped source must not be downloaded")

    summary = download_sources(tmp_path / "raw", tmp_path / "manifest.json", sources=(source,), opener=opener)

    assert summary["skipped"] == [source.name]
    assert summary["downloaded"] == []


def test_force_refreshes_existing_source(tmp_path: Path) -> None:
    source = OfficialSource("Refreshable source", "https://official.example/source.txt", "nist/source.txt", "TXT")
    target = tmp_path / "raw" / source.relative_path
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")

    summary = download_sources(
        tmp_path / "raw",
        tmp_path / "manifest.json",
        force=True,
        sources=(source,),
        opener=lambda request, timeout: FakeResponse(b"new"),
    )

    assert summary["downloaded"] == [source.name]
    assert target.read_text(encoding="utf-8") == "new"


def test_download_failure_is_reported_without_fabricating_file(tmp_path: Path) -> None:
    source = OfficialSource("Unavailable source", "https://official.example/missing", "cisa/missing.pdf", "PDF")

    summary = download_sources(
        tmp_path / "raw",
        tmp_path / "manifest.json",
        sources=(source,),
        opener=lambda request, timeout: FakeResponse(b"", status=503),
    )

    assert summary["counts"] == {"downloaded": 0, "skipped": 0, "failed": 1}
    assert not (tmp_path / "raw" / "cisa" / "missing.pdf").exists()
    assert summary["failed"][0]["source"] == source.name


def test_mitre_parser_is_deterministic_and_selective(tmp_path: Path) -> None:
    bundle = {
        "objects": [
            {"type": "attack-pattern", "id": "attack-pattern--2", "name": "Technique B", "description": "Second"},
            {"type": "attack-pattern", "id": "attack-pattern--1", "name": "Technique A", "x_mitre_detection": "Detect A"},
            {"type": "identity", "id": "identity--1", "name": "Not a knowledge object"},
        ]
    }
    source = tmp_path / "enterprise.json"
    source.write_text(json.dumps(bundle), encoding="utf-8")
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    assert parse_enterprise_attack(source, first_dir) == 2
    assert parse_enterprise_attack(source, second_dir) == 2
    first_files = sorted(first_dir.glob("*.md"))
    second_files = sorted(second_dir.glob("*.md"))
    assert [path.name for path in first_files] == [path.name for path in second_files]
    assert [path.read_text(encoding="utf-8") for path in first_files] == [path.read_text(encoding="utf-8") for path in second_files]
    assert all("Not a knowledge object" not in path.read_text(encoding="utf-8") for path in first_files)