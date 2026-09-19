# Knowledge Base

Place legitimate, appropriately licensed security documents in `raw/`. Supported
formats are `.txt`, `.md`, and `.pdf`. Do not place credentials, malware samples,
or fabricated threat-intelligence documents here.

The official-source bootstrap command can populate `raw/` from MITRE ATT&CK,
NIST CSF 2.0, OWASP Top 10:2025, and CISA CPG sources:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.rag.source_downloader
```

Source metadata is recorded in `../source_manifest.json`. The MITRE STIX bundle
is retained alongside deterministic per-object Markdown files under
`raw/mitre/parsed/` for normal ingestion.

The ingestion command writes derived JSONL chunks to `processed/`. Stage 4.2 writes
the local persistent Qdrant store to `vector_store/`. Local source documents,
processed output, and vector data remain untracked.
