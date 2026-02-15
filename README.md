# AirGap Lab AI

Containerized Retrieval-Augmented Generation platform for domain-specific AI assistants, designed for fully local lab use.
Each deployment can be configured for a different use case (prompt behavior, corpus, and model settings) while reusing the same stack.

## Platform Overview

Services:
- `ollama`: local model runtime and model storage
- `rag-api`: FastAPI backend for upload, ingestion, retrieval, and question answering
- `web-ui`: browser UI for operations and chat

Persistent storage:
- Uploaded corpus files: `./data` (mounted to `/workspace/data`)
- Vector index: `./index`
- Ollama models: Docker volume `ollama_data`

Default endpoints:
- UI: `http://localhost:8080`
- API: `http://localhost:8000`
- Ollama: `http://localhost:11434`

## Setup

### 1) Prerequisites

- Linux host with Docker Engine + Docker Compose plugin
- Recommended: 16–32 GB RAM for better 7B performance

### 2) Configure environment

```bash
cp .env.example .env
```

Common `.env` settings:
- `USE_CASE_NAME`: display/use-case identity
- `ASSISTANT_INSTRUCTIONS`: behavior/guardrails for the assistant
- `CORPUS_PATH`: corpus root inside container (default `/workspace/data/corpus`)
- `OLLAMA_MODEL`: `auto` (default) or pinned model tag
- `OFFLINE_STRICT`: `1` to disallow model pulls at startup

### 3) Start stack

```bash
docker compose up --build -d
```

### 4) Verify health

```bash
curl http://localhost:8000/health
```

### 5) Add documents and build index

Use UI:
- Open `http://localhost:8080`
- Upload files (`.md`, `.txt`, `.rst`, `.pdf`)
- Click **Ingest Corpus**

Or use API:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "files=@/path/to/doc1.pdf" \
  -F "files=@/path/to/doc2.md"

curl -X POST http://localhost:8000/ingest
```

### 6) Ask questions

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Your domain-specific question","top_k":4}'
```

## Administration

### Operational workflows

- **Check status**: `GET /health`
- **Upload corpus docs**: `POST /documents/upload`
- **List uploaded docs**: `GET /documents`
- **Delete one uploaded doc**: `DELETE /documents?stored_as=uploads/<file>`
- **Delete all uploaded docs**: `DELETE /documents/all`
- **Rebuild retrieval index**: `POST /ingest`

### Model management

- Auto mode (`OLLAMA_MODEL=auto`) selects model candidates by detected hardware profile.
- Pin model explicitly (example):

```bash
echo "OLLAMA_MODEL=mistral:7b" >> .env
```

- Strict offline operation:

```bash
echo "OFFLINE_STRICT=1" >> .env
echo "OLLAMA_AUTO_PULL=0" >> .env
```

- Preload model for offline mode:

```bash
docker exec -it airgap-ollama ollama pull mistral:7b
```

### Runtime tuning

Optional overrides in `.env`:
- `TOP_K`
- `MAX_CONTEXT_CHARS`
- `GEN_NUM_CTX`
- `GEN_NUM_PREDICT`
- `GEN_NUM_THREAD`
- `GEN_TEMPERATURE`

`/health` reports active tuning and environment-derived runtime values.

### Maintenance commands

```bash
# Restart stack
docker compose up --build -d

# View logs
docker compose logs -f rag-api
docker compose logs -f web-ui
docker compose logs -f ollama

# Stop stack
docker compose down
```

## Developer Guidance

### Repository structure

- `app/src/main.py`: API routes, prompt building, startup checks
- `app/src/config.py`: environment config + autotune wiring
- `app/src/ingest.py`: corpus scanning and chunk preparation
- `app/src/rag.py`: TF-IDF vectorization and retrieval
- `app/src/ollama_client.py`: model ensure/pull and generation calls
- `ui/index.html`: single-page operations + chat UI
- `docker-compose.yml`: service topology and persistence mounts

### Development workflow

```bash
# Validate Python syntax quickly
python3 -m compileall app/src

# Rebuild/restart after changes
docker compose up --build -d
```

### API contract summary

- `GET /health`
- `GET /documents`
- `POST /documents/upload` (multipart field name: `files`)
- `DELETE /documents?stored_as=uploads/<name>`
- `DELETE /documents/all`
- `POST /ingest`
- `POST /ask`

`POST /ask` request body example:

```json
{
  "question": "Your domain question",
  "top_k": 4
}
```

### Notes for extending features

- Keep corpus persistence under mounted `./data` paths.
- Re-run ingestion after corpus add/delete operations.
- If retrieval behavior changes, ensure `rag.py` and ingestion output stay schema-compatible.

## Troubleshooting

### `Secure Connection Failed` in browser

Cause:
- UI is served over HTTP by default, but browser attempts HTTPS.

Fix:
- Open `http://localhost:8080` (not `https://localhost:8080`).
- If browser forces HTTPS, clear localhost HSTS/HTTPS-only exception and retry.

### Web UI shows `Request failed` on Ask

Checks:
- Verify backend health: `curl http://localhost:8000/health`
- Ensure corpus is indexed: `POST /ingest` after upload/delete changes

Useful commands:

```bash
docker compose logs -f rag-api
docker compose logs -f web-ui
```

### Answers are generic or not grounded

Cause:
- Corpus was not ingested, is empty, or has low-quality/irrelevant docs.

Fix:
- Upload relevant documents, then run ingestion again.
- Lower `TOP_K` or tune context with `MAX_CONTEXT_CHARS` if responses are noisy.

### Startup fails in strict offline mode

Cause:
- `OFFLINE_STRICT=1` and required model is not cached locally.

Fix:

```bash
docker exec -it airgap-ollama ollama pull <model-tag>
docker compose up --build -d
```

Or disable strict mode in `.env`:
- `OFFLINE_STRICT=0`
- `OLLAMA_AUTO_PULL=1`

### Uploaded files do not appear

Checks:
- Confirm supported extensions: `.md`, `.txt`, `.rst`, `.pdf`
- Refresh document list in UI or call `GET /documents`
- Verify host persistence path: `./data/corpus/uploads`

### Changes not visible after edits

Fix:

```bash
docker compose up --build -d
```

Then hard-refresh browser (`Ctrl+Shift+R`).
