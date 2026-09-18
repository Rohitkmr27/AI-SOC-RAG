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
