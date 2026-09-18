# Knowledge Base

Place legitimate, appropriately licensed security documents in `raw/`. Supported
formats are `.txt`, `.md`, and `.pdf`. Do not place credentials, malware samples,
or fabricated threat-intelligence documents here.

The ingestion command writes derived JSONL chunks to `processed/`. Both directories
are retained in Git only through their `.gitkeep` files; local source documents and
processed output remain untracked.
