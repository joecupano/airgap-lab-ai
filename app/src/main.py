from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from .config import settings
from .ingest import build_index, is_supported_file
from .models import (
    AskRequest,
    AskResponse,
    IngestResponse,
    ListDocumentsResponse,
    SourceChunk,
    DeleteAllDocumentsResponse,
    DeleteDocumentResponse,
    UploadDocumentsResponse,
    UploadedFileItem,
)
from .ollama_client import ollama_client
from .rag import rag_store

app = FastAPI(title="AirGap Lab AI API", version="0.2.0")


@app.on_event("startup")
def startup_checks() -> None:
    try:
        allow_pull = settings.ollama_auto_pull and not settings.offline_strict
        selected_model = ollama_client.ensure_model(auto_pull=allow_pull)
        settings.ollama_model = selected_model
    except Exception as exc:
        if settings.offline_strict:
            raise RuntimeError(
                "Offline strict mode is enabled and no suitable local model is available. "
                "Preload the model with 'ollama pull <model>' and retry. "
                f"Details: {exc}"
            ) from exc
        raise RuntimeError(f"Unable to prepare Ollama model: {exc}") from exc


def _build_prompt(question: str, retrieved: list[SourceChunk]) -> str:
    context_blocks = []
    total_chars = 0
    for i, chunk in enumerate(retrieved, start=1):
        block = f"[{i}] source={chunk.source} chunk={chunk.chunk_id}\n{chunk.text}"
        if total_chars + len(block) > settings.max_context_chars:
            break
        context_blocks.append(block)
        total_chars += len(block)

    context_text = "\n\n".join(context_blocks) if context_blocks else "No context was retrieved."

    return (
        f"You are a specialist assistant for this use case: {settings.use_case_name}. "
        f"Follow these instructions: {settings.assistant_instructions}\n\n"
        f"CONTEXT:\n{context_text}\n\n"
        f"QUESTION:\n{question}\n\n"
        "Return a concise and useful answer with assumptions and practical guidance when relevant."
    )


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_", "."})
    return cleaned.strip(".") or "document"


def _uploads_dir() -> Path:
    root = Path(settings.corpus_path)
    upload_dir = root / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _list_uploaded_documents() -> list[UploadedFileItem]:
    root = Path(settings.corpus_path)
    upload_dir = _uploads_dir()
    docs: list[UploadedFileItem] = []
    for item in sorted(upload_dir.iterdir()):
        if not item.is_file():
            continue
        docs.append(
            UploadedFileItem(
                filename=item.name,
                stored_as=str(item.relative_to(root)),
                size_bytes=item.stat().st_size,
            )
        )
    return docs


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": settings.ollama_model,
        "index_ready": rag_store.exists(),
        "corpus_path": settings.corpus_path,
        "use_case_name": settings.use_case_name,
        "tuning_profile": settings.tuning_profile_name,
        "system_ram_gb": settings.system_ram_gb,
        "system_cpu_threads": settings.system_cpu_threads,
        "generation": {
            "num_ctx": settings.generation_num_ctx,
            "num_predict": settings.generation_num_predict,
            "num_thread": settings.generation_num_thread,
            "temperature": settings.generation_temperature,
        },
        "offline_strict": settings.offline_strict,
    }


@app.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    chunk_count, file_count = build_index()
    return IngestResponse(
        indexed_chunks=chunk_count,
        indexed_files=file_count,
        corpus_path=settings.corpus_path,
    )


@app.post("/documents/upload", response_model=UploadDocumentsResponse)
async def upload_documents(files: list[UploadFile] = File(...)) -> UploadDocumentsResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    root = Path(settings.corpus_path)
    upload_dir = _uploads_dir()

    uploaded: list[UploadedFileItem] = []
    rejected: list[str] = []

    for upload in files:
        filename = upload.filename or "document"
        if not is_supported_file(filename):
            rejected.append(filename)
            continue

        safe_name = _safe_filename(filename)
        target = upload_dir / f"{uuid4().hex[:8]}_{safe_name}"
        data = await upload.read()
        target.write_bytes(data)

        uploaded.append(
            UploadedFileItem(
                filename=filename,
                stored_as=str(target.relative_to(root)),
                size_bytes=len(data),
            )
        )

    return UploadDocumentsResponse(uploaded=uploaded, rejected=rejected, corpus_path=settings.corpus_path)


@app.get("/documents", response_model=ListDocumentsResponse)
def list_documents() -> ListDocumentsResponse:
    return ListDocumentsResponse(documents=_list_uploaded_documents(), corpus_path=settings.corpus_path)


@app.delete("/documents", response_model=DeleteDocumentResponse)
def delete_document(stored_as: str = Query(..., min_length=1)) -> DeleteDocumentResponse:
    root = Path(settings.corpus_path)
    upload_dir = _uploads_dir()
    target = (root / stored_as).resolve()

    try:
        target.relative_to(upload_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Only files under uploads/ can be deleted.") from exc

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")

    target.unlink()
    return DeleteDocumentResponse(deleted=stored_as, corpus_path=settings.corpus_path)


@app.delete("/documents/all", response_model=DeleteAllDocumentsResponse)
def delete_all_documents() -> DeleteAllDocumentsResponse:
    upload_dir = _uploads_dir()
    deleted_count = 0
    for item in upload_dir.iterdir():
        if item.is_file():
            item.unlink()
            deleted_count += 1
    return DeleteAllDocumentsResponse(deleted_count=deleted_count, corpus_path=settings.corpus_path)


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if not rag_store.exists():
        raise HTTPException(status_code=400, detail="No index found. Call POST /ingest first.")

    retrieved = rag_store.retrieve(request.question, top_k=request.top_k)
    source_chunks = [
        SourceChunk(source=r.source, chunk_id=r.chunk_id, text=r.text, score=r.score)
        for r in retrieved
    ]

    prompt = _build_prompt(request.question, source_chunks)
    answer = ollama_client.generate(prompt)

    return AskResponse(answer=answer, model=settings.ollama_model, sources=source_chunks)
