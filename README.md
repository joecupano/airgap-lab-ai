# AirGap Lab AI

Containerized Retrieval-Augmented Generation platform for domain-specific AI assistants, designed for fully local lab use. **No external AI services required** - all inference runs locally using Ollama.

Each deployment can be configured for a different use case (prompt behavior, corpus, and model settings) while reusing the same stack.

## Platform Overview

Services:
- `ollama`: local model runtime and model storage
- `rag-api`: FastAPI backend for upload, ingestion, retrieval, and question answering
- `web-ui`: browser UI (nginx) for operations and chat

Persistent storage:
- Uploaded corpus files: `./data/corpus` (mounted to `/workspace/data/corpus`)
- Vector index: `./index` (rebuildable from corpus)
- Ollama models: Docker volume `ollama_data`

Default endpoints:
- UI: `http://localhost:8080`
- API: `http://localhost:8000`
- Ollama: `http://localhost:11434`

## Setup

### 1) Prerequisites

- Linux host with Docker Engine + Docker Compose plugin
- Minimum: 8GB RAM (smaller models)
- Recommended: 16–32 GB RAM for 7B models
- Optional: NVIDIA GPU with CUDA for accelerated inference

### 2) Configure environment

Choose a configuration template based on your hardware:

```bash
# For 16GB RAM (CPU only)
cp .env.cpu-16gb .env

# For 32GB RAM (CPU only)
cp .env.cpu-32gb .env

# For 64GB RAM (CPU only)
cp .env.cpu-64gb .env

# For GPU with 6GB VRAM + 64GB RAM
cp .env.gpu-6gb-64gb .env

# Or start from the documented template
cp .env.template .env
```

Common `.env` settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | Model to use: `auto` or specific tag (e.g., `mistral:7b`) | `auto` |
| `OLLAMA_AUTO_PULL` | Allow automatic model downloads (`1`=yes, `0`=no) | `1` |
| `OFFLINE_STRICT` | Block all downloads even if auto-pull enabled (`1`=yes) | `0` |
| `USE_CASE_NAME` | Identity label in system prompt | `Domain Assistant` |
| `ASSISTANT_INSTRUCTIONS` | Behavioral guidelines for the AI | Sensible default |
| `CORPUS_PATH` | Document storage path in container | `/workspace/data/corpus` |

See `.env.template` for full documentation of all options.

### 3) Start stack

```bash
docker compose up --build -d
```

Optional scripted setup (same flow as above):

```bash
# Choose profile and run install flow
./install.sh cpu-16gb

# Optional GPU-safe startup (requires NVIDIA Container Toolkit)
./start-stack.sh --gpu

# Non-interactive GPU startup + auto-install toolkit if missing (Debian/Ubuntu)
./start-stack.sh --gpu --install-toolkit

# Force AMD GPU path (auto-detect is default)
./start-stack.sh --gpu --vendor=amd

# Fail fast if GPU verification does not pass
./start-stack.sh --gpu --strict-gpu-verify
```

When run with `--gpu`, `start-stack.sh` auto-detects NVIDIA/AMD and checks required container runtime prerequisites. On Debian/Ubuntu, it can prompt to install missing toolkit/runtime dependencies, or install automatically with `--install-toolkit`.
After startup, it prints a vendor-specific GPU verification status for the `airgap-ollama` container.
Use `--strict-gpu-verify` to make the script exit non-zero when verification fails.

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

Use UI:
- Open `http://localhost:8080`
- Enter your question in the chat box
- Submit to get an answer with retrieved context

Or use API:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Your domain-specific question","top_k":4}'
```

## Administration

### Operational workflows

Use the UI (`http://localhost:8080`) for day-to-day upload, ingest, and ask flows. Use API endpoints below for automation/integration.

- **Check status**: `GET /health`
- **Upload corpus docs**: `POST /documents/upload`
- **List uploaded docs**: `GET /documents`
- **Delete one uploaded doc**: `DELETE /documents?stored_as=uploads/<file>`
- **Delete all uploaded docs**: `DELETE /documents/all`
- **Rebuild retrieval index**: `POST /ingest`

### Model management

**Auto mode** (`OLLAMA_MODEL=auto`) selects models based on detected RAM:

| RAM | Profile | Model Candidates |
|-----|---------|------------------|
| ≤8GB | low | qwen2.5:1.5b, qwen2.5:3b |
| ≤16GB | medium | qwen2.5:3b, llama3.2:3b, mistral:7b |
| ≤24GB | balanced | mistral:7b, llama3.1:8b, qwen2.5:7b |
| >24GB | high | mistral:7b, qwen2.5:7b, llama3.1:8b |

**Pin a specific model:**

```bash
echo "OLLAMA_MODEL=mistral:7b" >> .env
```

**Strict offline operation** (for airgapped environments):

```bash
echo "OFFLINE_STRICT=1" >> .env
echo "OLLAMA_AUTO_PULL=0" >> .env
```

- Preload model for offline mode:

```bash
docker exec -it airgap-ollama ollama pull mistral:7b
```

### Runtime tuning

Performance parameters are auto-tuned based on system RAM. Override in `.env` if needed:

| Variable | Description | Auto-tuned |
|----------|-------------|------------|
| `TOP_K` | Number of document chunks retrieved per question | 3-5 by RAM |
| `MAX_CONTEXT_CHARS` | Max characters from retrieved chunks | 8000 |
| `GEN_NUM_CTX` | Model context window (tokens) | 1536-4096 by RAM |
| `GEN_NUM_PREDICT` | Max response tokens | 320-640 by RAM |
| `GEN_NUM_THREAD` | CPU threads for inference | min(cpu_count, 12) |
| `GEN_TEMPERATURE` | Response randomness (0.0-2.0) | 0.2 |

`/health` endpoint reports active tuning values.

### File upload limits

Maximum upload size: **250MB** per request (configurable in `ui/nginx.conf`).

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

```
├── app/
│   ├── src/
│   │   ├── main.py          # API routes, prompt building, startup checks
│   │   ├── config.py        # Environment config + autotune wiring
│   │   ├── autotune.py      # RAM-based profile detection
│   │   ├── ingest.py        # Corpus scanning and chunk preparation
│   │   ├── rag.py           # TF-IDF vectorization and retrieval
│   │   └── ollama_client.py # Model ensure/pull and generation calls
│   ├── Dockerfile
│   ├── requirements.txt
│   └── start.sh
├── ui/
│   ├── index.html           # Single-page operations + chat UI
│   ├── nginx.conf           # Nginx proxy configuration
│   └── Dockerfile
├── data/
│   └── corpus/              # Document storage (persistent)
│       └── uploads/         # User-uploaded files
├── index/                   # Vector index files (rebuildable)
├── docker-compose.yml       # Service topology and mounts
├── .env.template            # Documented configuration template
├── .env.cpu-16gb            # Optimized config for 16GB RAM
├── .env.cpu-32gb            # Optimized config for 32GB RAM
├── .env.cpu-64gb            # Optimized config for 64GB RAM
└── .env.gpu-6gb-64gb        # Optimized config for GPU + 64GB RAM
```

### Development workflow

```bash
# Validate Python syntax quickly
python3 -m compileall app/src

# Rebuild/restart after changes
docker compose up --build -d
```

### API contract summary

Question-answering is available in the UI at `http://localhost:8080` (chat), backed by `POST /ask`.

- `GET /health`
- `POST /ask`
- `GET /documents`
- `POST /documents/upload` (multipart field name: `files`)
- `DELETE /documents?stored_as=uploads/<name>`
- `DELETE /documents/all`
- `POST /ingest`

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
- Index files (`./index/`) are rebuildable - safe to delete and regenerate via "Ingest Corpus".

## Hardware Configuration Examples

### CPU-only systems

| RAM | Config File | Recommended Model | Context Window |
|-----|-------------|-------------------|----------------|
| 16GB | `.env.cpu-16gb` | qwen2.5:3b, mistral:7b | 2048 tokens |
| 32GB | `.env.cpu-32gb` | mistral:7b, llama3.1:8b | 4096 tokens |
| 64GB | `.env.cpu-64gb` | qwen2.5:14b | 8192 tokens |

### GPU-accelerated systems

| VRAM | RAM | Config File | Recommended Model | Context Window |
|------|-----|-------------|-------------------|----------------|
| 6GB | 64GB | `.env.gpu-6gb-64gb` | mixtral:8x7b | 16384 tokens |

**GPU notes:**
- Requires NVIDIA drivers and CUDA
- Ollama auto-detects GPU
- Models larger than VRAM will offload to system RAM (slower but works)
- Use Q4 quantized models for best VRAM efficiency

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

### 413 Request Entity Too Large

Cause:
- File upload exceeds nginx size limit.

Fix:
- Current limit is 250MB (configured in `ui/nginx.conf`).
- To increase, edit `client_max_body_size` in `ui/nginx.conf` and rebuild:

```bash
docker compose build web-ui && docker compose up -d web-ui
```

### Backend container keeps restarting

Cause:
- Usually a missing model when `OFFLINE_STRICT=1`.

Check logs:

```bash
docker logs airgap-rag-api --tail 30
```

Fix:
- Pull the required model: `docker exec airgap-ollama ollama pull <model>`
- Or set `OFFLINE_STRICT=0` and `OLLAMA_AUTO_PULL=1` in `.env`
- Then restart: `docker compose up -d rag-api`

## License

MIT
