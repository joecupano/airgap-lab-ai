from pathlib import Path

from .config import settings
from .rag import rag_store
from .utils import chunk_text, read_pdf_file, read_text_file


SUPPORTED_EXT = {".txt", ".md", ".rst", ".pdf"}


def is_supported_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXT


def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf_file(path)
    return read_text_file(path)


def build_index(corpus_path: str | None = None) -> tuple[int, int]:
    root = Path(corpus_path or settings.corpus_path)
    root.mkdir(parents=True, exist_ok=True)

    chunks: list[dict] = []
    indexed_files = 0

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXT:
            continue

        text = _extract_text(file_path)
        chunk_list = chunk_text(text)
        if not chunk_list:
            continue

        indexed_files += 1
        for chunk_id, chunk in enumerate(chunk_list, start=1):
            chunks.append(
                {
                    "source": str(file_path.relative_to(root)),
                    "chunk_id": chunk_id,
                    "text": chunk,
                }
            )

    if chunks:
        rag_store.save(chunks)

    return len(chunks), indexed_files
