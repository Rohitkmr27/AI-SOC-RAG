"""Download and normalize official cybersecurity knowledge sources."""

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from app.rag.config import DEFAULT_RAW_DIRECTORY, DEFAULT_SOURCE_MANIFEST
from app.rag.mitre_parser import parse_enterprise_attack

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class OfficialSource:
    name: str
    url: str
    relative_path: str
    source_type: str
    version: str | None = None
    parser: str | None = None


OFFICIAL_SOURCES = (
    OfficialSource(
        name="MITRE ATT&CK Enterprise",
        url="https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json",
        relative_path="mitre/enterprise-attack.json",
        source_type="STIX JSON",
        parser="mitre_enterprise",
    ),
    OfficialSource(
        name="NIST Cybersecurity Framework 2.0",
        url="https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        relative_path="nist/nist-csf-2.0.pdf",
        source_type="PDF",
        version="2.0",
    ),
    OfficialSource(
        name="OWASP Top 10:2025",
        url="https://owasp.org/Top10/2025/",
        relative_path="owasp/owasp-top-10-2025.md",
        source_type="Official HTML converted to Markdown",
        version="2025",
        parser="owasp_html",
    ),
    OfficialSource(
        name="CISA Cross-Sector Cybersecurity Performance Goals",
        url="https://www.cisa.gov/sites/default/files/2023-08/cisa-cross-sector-cybersecurity-performance-goals.pdf",
        relative_path="cisa/cisa-cpg.pdf",
        source_type="PDF",
        version="1.0",
    ),
)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag.lower() in {"p", "div", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag.lower() in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)

    def markdown(self) -> str:
        lines = []
        for line in "".join(self.parts).splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if line and (not lines or lines[-1] != line):
                lines.append(line)
        return "\n\n".join(lines) + "\n"


def _download(url: str, timeout: int, opener: Callable[..., Any] = urlopen) -> bytes:
    request = Request(url, headers={"User-Agent": "AI-SOC-RAG official-source downloader"})
    with opener(request, timeout=timeout) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"HTTP status {response.status} from {url}")
        return response.read()


def _write_source(source: OfficialSource, content: bytes, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.parser == "owasp_html":
        parser = _VisibleTextParser()
        parser.feed(content.decode("utf-8", errors="replace"))
        target.write_text(parser.markdown(), encoding="utf-8", newline="\n")
    else:
        target.write_bytes(content)


def _metadata(source: OfficialSource, target: Path, timestamp: str) -> dict[str, Any]:
    return {
        "source_name": source.name,
        "official_url": source.url,
        "local_filename": target.as_posix(),
        "download_timestamp": timestamp,
        "source_type": source.source_type,
        "version": source.version,
    }


def download_sources(
    raw_directory: Path = DEFAULT_RAW_DIRECTORY,
    manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
    force: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    sources: tuple[OfficialSource, ...] = OFFICIAL_SOURCES,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    raw_directory.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    summary: dict[str, Any] = {"downloaded": [], "skipped": [], "failed": []}
    for source in sources:
        target = raw_directory / source.relative_path
        try:
            if target.exists() and not force:
                summary["skipped"].append(source.name)
                continue
            content = _download(source.url, timeout, opener)
            _write_source(source, content, target)
            if source.parser == "mitre_enterprise":
                parse_enterprise_attack(target, target.parent / "parsed")
            timestamp = datetime.now(timezone.utc).isoformat()
            existing[source.name] = _metadata(source, target.relative_to(raw_directory), timestamp)
            summary["downloaded"].append(source.name)
        except Exception as error:
            logger.error("Unable to download %s: %s", source.name, error)
            summary["failed"].append({"source": source.name, "error": str(error)})
    manifest_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    summary["counts"] = {key: len(value) for key, value in summary.items() if key != "counts"}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official cybersecurity knowledge sources.")
    parser.add_argument("--force", action="store_true", help="Refresh existing source files.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    print(json.dumps(download_sources(force=args.force, timeout=args.timeout), indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()