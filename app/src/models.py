from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int | None = Field(default=None, ge=1, le=12)


class SourceChunk(BaseModel):
    source: str
    chunk_id: int
    text: str
    score: float


class AskResponse(BaseModel):
    answer: str
    model: str
    sources: list[SourceChunk]


class IngestResponse(BaseModel):
    indexed_chunks: int
    indexed_files: int
    corpus_path: str


class UploadedFileItem(BaseModel):
    filename: str
    stored_as: str
    size_bytes: int


class UploadDocumentsResponse(BaseModel):
    uploaded: list[UploadedFileItem]
    rejected: list[str]
    corpus_path: str


class ListDocumentsResponse(BaseModel):
    documents: list[UploadedFileItem]
    corpus_path: str


class DeleteDocumentResponse(BaseModel):
    deleted: str
    corpus_path: str


class DeleteAllDocumentsResponse(BaseModel):
    deleted_count: int
    corpus_path: str
