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

Stage 4 creates only the local document-ingestion foundation for a future RAG system. It does not include embeddings, a vector database, retrieval, an LLM, an analyst, or an agent.

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

No IDS, machine learning, RAG, vector database, LLM, agents, threat intelligence, dashboard, or PostgreSQL functionality is implemented at this stage.

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
