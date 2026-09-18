# RAG-Enhanced AI-Driven Security Operations Center

This repository contains the initial setup for a final-year BTech project. Stage 1 provides only a FastAPI backend health endpoint and a React + Vite frontend confirmation page.

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
