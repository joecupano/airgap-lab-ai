import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import load_npz, save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import settings


@dataclass
class RetrievedChunk:
    source: str
    chunk_id: int
    text: str
    score: float


class RagStore:
    def __init__(self, store_path: str):
        self.store_dir = Path(store_path)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.vectorizer_path = self.store_dir / "vectorizer.joblib"
        self.matrix_path = self.store_dir / "matrix.npz"
        self.metadata_path = self.store_dir / "metadata.json"

    def save(self, chunks: list[dict]) -> None:
        texts = [chunk["text"] for chunk in chunks]
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=50000)
        matrix = vectorizer.fit_transform(texts)

        joblib.dump(vectorizer, self.vectorizer_path)
        save_npz(self.matrix_path, matrix)
        self.metadata_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")

    def exists(self) -> bool:
        return self.vectorizer_path.exists() and self.matrix_path.exists() and self.metadata_path.exists()

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if not self.exists():
            return []

        vectorizer: TfidfVectorizer = joblib.load(self.vectorizer_path)
        matrix = load_npz(self.matrix_path)
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))

        q_vec = vectorizer.transform([query])
        scores = (matrix @ q_vec.T).toarray().ravel()
        if scores.size == 0:
            return []

        requested_k = top_k or settings.top_k
        k = max(1, min(int(requested_k), int(scores.size)))

        if k == scores.size:
            top_idx = np.argsort(scores)[::-1]
        else:
            kth = scores.size - k
            top_idx = np.argpartition(scores, kth)[-k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

        results: list[RetrievedChunk] = []
        for idx in top_idx:
            score = float(scores[idx])
            if score <= 0:
                continue
            row = metadata[idx]
            results.append(
                RetrievedChunk(
                    source=row["source"],
                    chunk_id=row["chunk_id"],
                    text=row["text"],
                    score=score,
                )
            )
        return results


rag_store = RagStore(settings.vector_store_path)
