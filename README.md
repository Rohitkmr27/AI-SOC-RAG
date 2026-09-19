# RAG-Enhanced AI-Driven Security Operations Center

This repository contains the initial setup for a final-year BTech project. Stage 1 provides only a FastAPI backend health endpoint and a React + Vite frontend confirmation page.

## Stage 2: Traditional IDS

The IDS uses the official [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) flow dataset. Download `MachineLearningCSV.zip` from that page and extract it under `data\raw\cicids2017\`. The loader searches recursively, so the expected result is, for example, `data\raw\cicids2017\MachineLearningCVE\*.csv`.

The CSV target is normalized to `Label`. The pipeline strips headers and labels, replaces infinite values, removes exact duplicates, retains missing feature values for pipeline imputation, excludes flow/IP/timestamp identifiers to reduce capture-specific leakage, uses a stratified 80/20 split with random state 42, and fits preprocessing only on training data. The saved joblib artifact contains both preprocessing and the Random Forest classifier.

Severity is project-level triage guidance only: it maps known attack labels to Informational/Medium/High/Critical, and downgrades malicious predictions below 0.60 model confidence to Low. It is not a certified risk score.

Train after extracting the real data:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.ids.train
```

Evaluate the saved model against the deterministic held-out split:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.ids.evaluate
```

The actual `evaluation_metrics.json` and `confusion_matrix.csv` are written to `backend\artifacts\ids\` and are intentionally ignored by Git.

## Stage 3: PostgreSQL alert management

Install PostgreSQL 16 or later, then create a local development role and database from `psql` as a PostgreSQL administrator:

```sql
CREATE USER ai_soc_user WITH PASSWORD 'replace-with-a-local-secret';
CREATE DATABASE ai_soc_rag OWNER ai_soc_user;
```

Set the connection string only in your shell or an untracked `.env` file:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://ai_soc_user:replace-with-a-local-secret@localhost:5432/ai_soc_rag'
```

Apply the initial schema migration from the repository root:

```powershell
python -m alembic upgrade head
```

The `alerts` table stores UUID IDs; event, creation, and update timestamps; IP addresses; ports; protocol; model attack type/confidence/severity; workflow status; and description. Valid statuses are `NEW`, `TRIAGED`, `INVESTIGATING`, and `RESOLVED`. The API validates IPs, port range, confidence range, severity, status, and required text.

Start the backend after setting `DATABASE_URL`:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m uvicorn app.main:app --reload
```

Alert APIs:

- `POST /alerts` — create a structured alert.
- `GET /alerts?severity=High&status=NEW&attack_type=PortScan` — list and filter alerts.
- `GET /alerts/{alert_id}` — retrieve an alert.
- `PATCH /alerts/{alert_id}` — update only status, severity, or description.
- `POST /alerts/from-ids` — run the existing trained IDS on supplied flow features and save that real prediction as an alert.

Example alert request:

```powershell
$body = '{"timestamp":"2026-09-19T10:00:00Z","source_ip":"192.0.2.10","destination_ip":"198.51.100.20","source_port":51515,"destination_port":443,"protocol":"TCP","attack_type":"PortScan","confidence":0.91,"severity":"Medium","description":"Network-flow alert."}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/alerts -ContentType 'application/json' -Body $body
```

The test suite uses only an in-memory SQLite database through dependency overrides; it neither reads nor changes the development PostgreSQL database.

## Stage 4: RAG document-ingestion foundation

Stage 4 creates the local document-ingestion foundation for a future RAG system. It writes deterministic JSONL chunks and does not include an LLM, analyst, or agent.

```text
data/knowledge_base/
├── raw/        # Add legitimate, appropriately licensed .txt, .md, or .pdf documents here
├── processed/  # Locally generated JSONL chunks
└── README.md
```

Run ingestion from the backend directory:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.rag.document_loader
```

The command discovers documents recursively under `data\knowledge_base\raw`, records unreadable or unsupported files without aborting the run, and writes deterministic JSONL chunks to `data\knowledge_base\processed\chunks.jsonl`.

Defaults are a 1,000-character target chunk size and 200-character word-boundary overlap. Change them when running the command if needed:

```powershell
python -m app.rag.document_loader --chunk-size 800 --chunk-overlap 150
```

Do not add fabricated threat intelligence, secrets, or malware samples. Only add documents you are permitted to use; raw documents and generated chunks remain untracked.

After training, send a prediction request using feature names from the downloaded CSV:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ids/predict -ContentType 'application/json' -Body '{"features":{"Destination Port":80,"Flow Duration":12345,"Total Fwd Packets":5,"Total Backward Packets":4}}'
```

Stage 4 does not modify IDS, machine learning, alert, PostgreSQL, or API functionality, and does not add generation, an LLM, agents, threat intelligence, or a dashboard.

## Stage 4.2: Embeddings, vector database, and indexing

Stage 4.2 embeds the existing `data\knowledge_base\processed\chunks.jsonl` file with the local CPU-compatible `sentence-transformers/all-MiniLM-L6-v2` model. Vectors are normalized for cosine similarity and stored in a persistent, Docker-free Qdrant local store:

```text
data/knowledge_base/vector_store/
```

The first embedding run downloads the model from Hugging Face if it is not already present in the local Sentence Transformers cache. No API key or external embedding API is used. After that download, indexing and search can run offline. The model is loaded lazily, so ingestion-only commands do not load it.

Install the backend dependencies, generate Stage 4 chunks if needed, then index them from `backend`:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.rag.index
```

Search the indexed chunks with the same model:

```powershell
python -m app.rag.search "what is a brute force attack"
python -m app.rag.search "what is a brute force attack" --top-k 3 --score-threshold 0.4
```

Indexing safely recreates the `security_knowledge_chunks` collection and reports the indexed chunk count and actual embedding dimension. Search returns similarity scores and the original chunk metadata, including source, file name, title when present, and content. The vector store and generated chunks are local derived data and remain untracked.

Limitations: retrieval quality depends on the legitimate documents placed in the knowledge base; the small MiniLM model is not domain-specialized; Qdrant local mode is intended for development and single-process local use; and this stage deliberately adds no generation, LLM, agent, dashboard, or authentication behavior.

## Stage 4.3: Official knowledge-base bootstrap

Stage 4.3 downloads source material from official locations only. The configured sources are:

- MITRE ATT&CK Enterprise STIX data from the official MITRE ATT&CK STIX repository.
- NIST Cybersecurity Framework 2.0 from an official NIST publication URL.
- OWASP Top 10:2025 from the official OWASP project page.
- CISA Cross-Sector Cybersecurity Performance Goals from an official CISA PDF URL.

Run the downloader from the backend directory:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.rag.source_downloader
```

Use `--force` to refresh files that already exist, or `--timeout 60` to change the per-request timeout:

```powershell
python -m app.rag.source_downloader --force --timeout 60
```

The command creates the source directories under `data\knowledge_base\raw\`, skips existing files unless forced, and prints JSON counts for downloaded, skipped, and failed sources. It records source name, official URL, local filename, UTC download timestamp, source type, and known version in `data\knowledge_base\source_manifest.json`. Failed downloads are reported and never replaced with fabricated content.

MITRE's official STIX JSON is retained at `data\knowledge_base\raw\mitre\enterprise-attack.json`. The downloader also deterministically creates one Markdown file per selected technique, tactic, group, software, or mitigation under `data\knowledge_base\raw\mitre\parsed\` so the existing TXT/Markdown/PDF ingestion flow does not turn the entire STIX bundle into one giant chunk. This is a structured transformation of downloaded STIX fields, not a manual summary.

After downloading or refreshing sources, run the existing ingestion and index commands:

```powershell
python -m app.rag.document_loader
python -m app.rag.index
```

The generated `chunks.jsonl`, local Qdrant store, source manifest, downloaded documents, and MITRE parsed output are local derived data. They should not be blindly committed to Git, especially the large MITRE dataset or vector database. The downloader code, configuration, tests, and documentation are the tracked project artifacts.

## Stage 5: RAG Answer Generation

Stage 5 connects the Stage 4.2 semantic retrieval engine to an LLM to generate strictly grounded cybersecurity answers with preserved source citations.

### Architecture

```text
User question
    ↓
Existing semantic search (Qdrant + all-MiniLM-L6-v2)
    ↓
Top-K relevant Qdrant chunks
    ↓
Bounded context construction
    ↓
LLM (Google Gemini via REST API)
    ↓
Grounded answer + source citations
```

### Environment Configuration

Configure the Gemini API key in your environment or local `.env` file:

```powershell
$env:GEMINI_API_KEY = "your-api-key-here"
# Optional model override (default: gemini-2.5-flash):
$env:GEMINI_MODEL = "gemini-2.5-flash"
```

The system does not fail on import when `GEMINI_API_KEY` is omitted. If retrieval succeeds but the key is not set, the CLI displays the retrieved sources and informs the operator that generation requires `GEMINI_API_KEY`.

### CLI Usage

From the `backend` directory:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m app.rag.generate "What is a brute force attack?"
```

Supported options:

```powershell
python -m app.rag.generate "What is a brute force attack?" --top-k 3 --score-threshold 0.4 --json
```

- `--top-k`: Number of chunks to retrieve (default: 5).
- `--score-threshold`: Optional similarity score cutoff.
- `--max-context-chars`: Maximum context character budget (default: 12000).
- `--model`: Gemini model override (defaults to `GEMINI_MODEL` or `gemini-2.5-flash`).
- `--json`: Output full structured JSON response.

### API Usage

Start the backend:

```powershell
Set-Location C:\AI-SOC-RAG\backend
python -m uvicorn app.main:app --reload
```

Endpoint: `POST /rag/query`

Example request:

```json
{
  "query": "What is a brute force attack?",
  "top_k": 3,
  "score_threshold": 0.3
}
```

Example response:

```json
{
  "answer": "Based on the retrieved security knowledge, a brute force attack involves an adversary systematically guessing passwords using a repetitive or iterative mechanism. It can occur via service interaction or offline against obtained credential data.",
  "sources": [
    {
      "source": "mitre/parsed/techniques-attack-pattern--a93494bb-4b80-4ea1-8695-3236a49916fd.md",
      "file_name": "techniques-attack-pattern--a93494bb-4b80-4ea1-8695-3236a49916fd.md",
      "document_id": "ff05859ed52021ae429ae330a872afbd5dccd9cdf2f59e723713826c6f0996cd",
      "chunk_id": "669082063f09c83d997279ccd5133530f0fe7b48f30878da6be5606bf3b2855f",
      "chunk_index": 2,
      "score": 0.5168,
      "title": null
    }
  ]
}
```

### Hallucination Guard and Empty Retrieval

- The system prompt strictly restricts answers to the supplied retrieved security knowledge.
- If semantic retrieval finds no matching chunks (or all chunks fall below `--score-threshold`), the system returns:
  `"I could not find sufficient information in the security knowledge base to answer this question."`
  with an empty source list, without calling the LLM.

### Limitations

- Answers are strictly limited to the ingested official cybersecurity sources (MITRE ATT&CK, NIST CSF 2.0, OWASP Top 10, CISA CPG).
- Live generation requires a valid `GEMINI_API_KEY` and internet access to the Google Gemini endpoint.
- This stage provides direct question-answering only; it intentionally does not include multi-agent workflows, autonomous tool execution, alert correlation, or a frontend chat dashboard.

## Stage 6: IDS Alert Intelligence / RAG Alert Enrichment

Stage 6 connects the Stage 3 PostgreSQL alert management pipeline with the Stage 4.2 Qdrant retrieval and Stage 5 Gemini LLM layer to enrich detected alerts with grounded cybersecurity intelligence and structured SOC analyst recommendations.

### Architecture

```text
IDS Alert
    ↓
Alert Retrieval
    ↓
Security Query Construction
    ↓
Qdrant Retrieval
    ↓
Grounded Context
    ↓
Gemini (Strict Analyst Prompt)
    ↓
SOC Analyst Enrichment
```

### API Usage: Alert Enrichment

Endpoint: `POST /alerts/{alert_id}/enrich`

This endpoint:
1. Loads the alert from PostgreSQL by ID (returns 404 if not found).
2. Synthesizes a cybersecurity search query from alert attributes (attack type, protocol, destination port, source port).
3. Performs semantic retrieval against the local Qdrant collection (`security_knowledge_chunks`).
4. Invokes the LLM with a strict SOC analyst prompt that strictly separates observed facts, retrieved context, and recommended investigation steps.
5. Returns a structured JSON response without permanently altering the underlying alert record.

Example request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/alerts/123e4567-e89b-12d3-a456-426614174000/enrich
```

Example response:

```json
{
  "alert": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "timestamp": "2026-09-19T10:00:00Z",
    "source_ip": "192.0.2.10",
    "destination_ip": "198.51.100.20",
    "source_port": 51515,
    "destination_port": 443,
    "protocol": "TCP",
    "attack_type": "PortScan",
    "confidence": 0.91,
    "severity": "Medium",
    "status": "NEW",
    "description": "Network-flow alert."
  },
  "analysis": {
    "summary": "PortScan alert indicates systematic reconnaissance targeting destination port 443.",
    "observed_indicators": [
      "TCP SYN activity targeting port 443",
      "High confidence model score (0.91)"
    ],
    "security_context": [
      "MITRE ATT&CK T1046: Network Service Discovery",
      "Adversaries systematically probe ports to map active listening services."
    ],
    "investigation_steps": [
      "Inspect firewall logs for packet bursts from source IP 192.0.2.10.",
      "Verify if destination service responded with SYN-ACK or RST."
    ],
    "recommended_mitigations": [
      "Enforce rate-limiting on inbound perimeter interfaces.",
      "Ensure unneeded exposed ports are closed."
    ]
  },
  "sources": [
    {
      "source": "mitre/parsed/techniques-attack-pattern--t1046.md",
      "file_name": "t1046.md",
      "document_id": "doc_ps",
      "chunk_id": "chunk_t1046",
      "chunk_index": 1,
      "score": 0.88,
      "title": "Network Service Discovery"
    }
  ]
}
```

### Advisory Grounding and Safety

- **Decision-Support Only**: Generated alert analyses are advisory triage aids for security analysts. They do not trigger automated firewall blocking or intrusive remediations.
- **Strict Grounding**: The analyst prompt forbids inventing attack attribution, fake incidents, or unverified MITRE IDs. It explicitly instructs the model never to assert an alert proves a compromise unless verified by facts.
- **Empty Retrieval Fallback**: If no relevant knowledge base chunks match the alert, a grounded fallback summary is returned without querying the LLM.

### Testing Instructions

Run alert enrichment tests:

```powershell
python -m pytest tests/test_alert_enrichment.py
```

Run the complete test suite:

```powershell
python -m pytest -q
```

## Stage 7: Alert Correlation and Deterministic Risk Scoring

Stage 7 clusters individual PostgreSQL alerts into correlated incident campaigns and calculates an explainable, bounded risk score (0–100) using purely deterministic security rules without using LLMs or machine learning heuristics for risk computation.

### Architecture

```text
Multiple IDS Alerts
        ↓
PostgreSQL Database
        ↓
Correlation Engine (BFS Connected Components)
        ↓
Related Alert Groups (Incidents)
        ↓
Deterministic Risk Scoring (0–100)
        ↓
Incident Summary
```

### Correlation Rule & Time Window

- **Time Window**: Default correlation window is **15 minutes** (configurable via `--correlation-window-minutes`).
- **Deterministic Rule**: Two alerts are linked if:
  1. They occur within the correlation window (`abs(timestamp_1 - timestamp_2) <= window_minutes`).
  2. **AND** they share `source_ip` **OR** `destination_ip`.
- Connected components (graph BFS) group indirectly linked alerts into unified Incident objects.
- Alerts within each incident are deterministically ordered by timestamp (ascending) with stable tie-breaking using the UUID string representation.

### Risk Scoring Formula & Factors

The risk score is computed from explicit, explainable security properties:

$$\text{Risk Score} = \text{min}\left(100, \max\left(0, \text{Base Severity} + \text{Confidence} + \text{Volume} + \text{Diversity} + \text{Repeated Source} + \text{Temporal Concentration}\right)\right)$$

1. **Base Severity Weight**: Highest severity alert in the incident (`Informational`=10, `Low`=25, `Medium`=50, `High`=75, `Critical`=100).
2. **Confidence Contribution**: $\text{int}(\text{Average Confidence} \times 15)$ (up to +15 pts).
3. **Alert Volume Contribution**: $\min((\text{alert\_count} - 1) \times 10, 25)$ (up to +25 pts).
4. **Attack Diversity Contribution**: $\min((\text{distinct\_attack\_types} - 1) \times 10, 20)$ (up to +20 pts).
5. **Repeated Source IP**: +10 pts if any source IP generates multiple alerts in the incident.
6. **Temporal Concentration**: +10 pts if multiple alerts occur within 5 minutes.

> **Risk Score Disclaimer**: The risk score is a deterministic prioritization heuristic. It is not a probability of compromise and has not been clinically, statistically, or operationally validated as such.

### API Usage

Fetch correlated incidents:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/alerts/correlations?lookback_minutes=60&correlation_window_minutes=15&minimum_risk_score=50"
```

Example response:

```json
{
  "incidents": [
    {
      "incident_id": "a1b2c3d4-e5f6-5a6b-7c8d-9e0f1a2b3c4d",
      "alert_count": 2,
      "first_seen": "2026-09-19T10:00:00Z",
      "last_seen": "2026-09-19T10:10:00Z",
      "source_ips": ["192.0.2.55"],
      "destination_ips": ["198.51.100.88", "198.51.100.89"],
      "attack_types": ["BruteForce", "PortScan"],
      "risk_score": 100,
      "risk_factors": [
        "Base severity: High (75 pts)",
        "High model confidence (avg: 0.90)",
        "Multiple correlated alerts (2 alerts in incident)",
        "Multiple distinct attack types observed (2 types: BruteForce, PortScan)",
        "Repeated source IP activity"
      ],
      "alert_ids": [
        "123e4567-e89b-12d3-a456-426614174000",
        "223e4567-e89b-12d3-a456-426614174001"
      ]
    }
  ],
  "total_incidents": 1,
  "total_correlated_alerts": 2,
  "lookback_minutes": 60,
  "correlation_window_minutes": 15
}
```

### Testing Instructions

Run alert correlation tests:

```powershell
python -m pytest tests/test_alert_correlation.py
```

Run full test suite:

```powershell
python -m pytest -q
```

## Stage 8: AI SOC Incident Investigation Engine

Stage 8 synthesizes correlated incident campaign data from Stage 7 with grounded multi-chunk RAG cyber intelligence from Stage 4.2 to generate structured, explainable AI SOC investigation reports.

### Architecture

```text
Correlated Incident Campaign (Stage 7)
        ↓
Incident Query Synthesis (Attack Types, Ports, Protocols)
        ↓
Qdrant Vector Retrieval (security_knowledge_chunks)
        ↓
Bounded Multi-Chunk Grounded Context
        ↓
Gemini LLM (Strict Analyst System Prompt)
        ↓
Structured Incident Investigation Report
```

### API Usage

Endpoint: `POST /alerts/correlations/{incident_id}/investigate`

Query Parameters:
- `lookback_minutes`: Minutes of historical alert data to fetch (default: 60).
- `correlation_window_minutes`: Incident correlation grouping window (default: 15).
- `top_k`: Maximum retrieved cybersecurity chunks (default: 5).

Example request:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/alerts/correlations/a1b2c3d4-e5f6-5a6b-7c8d-9e0f1a2b3c4d/investigate?top_k=5"
```

Example response:

```json
{
  "incident": {
    "incident_id": "a1b2c3d4-e5f6-5a6b-7c8d-9e0f1a2b3c4d",
    "alert_count": 2,
    "first_seen": "2026-09-19T10:00:00Z",
    "last_seen": "2026-09-19T10:10:00Z",
    "source_ips": ["192.0.2.10"],
    "destination_ips": ["198.51.100.20"],
    "attack_types": ["PortScan", "SSH-Bruteforce"],
    "risk_score": 85,
    "risk_factors": ["Base severity: High (75 pts)", "Multiple distinct attack types observed"],
    "alert_ids": ["123e4567-e89b-12d3-a456-426614174000", "223e4567-e89b-12d3-a456-426614174001"]
  },
  "investigation": {
    "executive_summary": "Correlated incident campaign involving initial PortScan reconnaissance followed by SSH-Bruteforce authentication attempts from 192.0.2.10.",
    "observed_evidence": [
      "Correlated Alert Count: 2",
      "Observed Attack Types: PortScan, SSH-Bruteforce",
      "Deterministic Risk Score: 85 / 100"
    ],
    "threat_context": [
      "Adversaries perform network service discovery (T1046) to identify listening SSH endpoints before initiating credential brute force (T1110)."
    ],
    "investigation_priorities": [
      "Verify SSH authentication logs on destination 198.51.100.20 for successful logins from 192.0.2.10.",
      "Check firewall logs for concurrent network probes targeting other high-value internal assets."
    ],
    "recommended_actions": [
      "Confirm connection state and session duration for SSH attempts.",
      "Inspect source IP 192.0.2.10 against external threat intelligence blocklists."
    ],
    "mitigations": [
      "Temporarily drop inbound traffic from 192.0.2.10 at perimeter firewall.",
      "Enforce fail2ban and rate-limiting on port 22."
    ],
    "mitre_context": [
      "MITRE ATT&CK T1110: Brute Force",
      "MITRE ATT&CK T1046: Network Service Discovery"
    ],
    "limitations": [
      "Analysis is advisory decision-support based on retrieved knowledge base sources.",
      "Does not execute automated network remediation."
    ]
  },
  "sources": [
    {
      "source": "mitre/parsed/techniques-attack-pattern--t1110.md",
      "file_name": "t1110.md",
      "document_id": "doc_bf",
      "chunk_id": "chunk_t1110",
      "chunk_index": 1,
      "score": 0.92,
      "title": "Brute Force"
    }
  ]
}
```

### Safety & Analytical Boundaries

- **Advisory Support Only**: Investigation reports provide grounded decision-support for human SOC analysts. The system performs no autonomous firewall blocking or host remediation.
- **Risk Score Immutability**: The LLM cannot alter or question the deterministic risk score (0–100), alert count, or severity calculated by Stage 7 rules.
- **Strict Grounding Guard**: Prompts strictly prohibit inventing evidence, attack attribution, or fake MITRE ATT&CK technique IDs.
- **Empty Retrieval Fallback**: If semantic search returns zero matching chunks from Qdrant, an explicit fallback investigation report is returned without making an LLM API call.

### Testing Instructions

Run incident investigation tests:

```powershell
python -m pytest tests/test_incident_investigation.py
```

Run full test suite:

```powershell
python -m pytest -q
```



## Prerequisites

- Python 3.11 or later
- Node.js 20 or later (includes npm)

## Install dependencies on Windows (PowerShell)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r backend\requirements-dev.txt

Set-Location frontend
npm install
Set-Location ..
```

If PowerShell prevents activation, run this once for the current shell and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run the backend

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/health. Expected response:

```json
{"status":"ok","service":"ai-soc-rag-backend"}
```

## Run the frontend

In a second PowerShell window:

```powershell
Set-Location frontend
npm run dev
```

Vite prints the local URL (normally http://localhost:5173). Open it in a browser.

## Test the backend

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests
```
