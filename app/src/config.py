import os

from .autotune import detect_profile


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


class Settings:
    def __init__(self) -> None:
        profile = detect_profile()
        self.tuning_profile_name: str = profile.name
        self.system_ram_gb: int = profile.ram_gb
        self.system_cpu_threads: int = profile.cpu_threads
        self.model_candidates: list[str] = profile.model_candidates

        self.ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "auto")
        self.ollama_auto_pull: bool = os.getenv("OLLAMA_AUTO_PULL", "1") == "1"
        self.offline_strict: bool = os.getenv("OFFLINE_STRICT", "0") == "1"
        self.vector_store_path: str = os.getenv("VECTOR_STORE_PATH", "/workspace/index")
        self.corpus_path: str = os.getenv(
            "CORPUS_PATH",
            os.getenv("RF_CORPUS_PATH", "/workspace/data/corpus"),
        )
        self.use_case_name: str = os.getenv("USE_CASE_NAME", "Domain Assistant")
        self.assistant_instructions: str = os.getenv(
            "ASSISTANT_INSTRUCTIONS",
            (
                "Answer using the provided context when possible. "
                "If context is insufficient, state what is missing and provide a cautious best-effort answer."
            ),
        )

        self.top_k: int = _env_int("TOP_K", profile.top_k)
        self.max_context_chars: int = _env_int("MAX_CONTEXT_CHARS", 8000)

        self.generation_temperature: float = _env_float("GEN_TEMPERATURE", 0.2)
        self.generation_num_ctx: int = _env_int("GEN_NUM_CTX", profile.num_ctx)
        self.generation_num_predict: int = _env_int("GEN_NUM_PREDICT", profile.num_predict)
        self.generation_num_thread: int = _env_int("GEN_NUM_THREAD", min(profile.cpu_threads, 12))


settings = Settings()
