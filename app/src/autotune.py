import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TuningProfile:
    name: str
    ram_gb: int
    cpu_threads: int
    model_candidates: list[str]
    num_ctx: int
    num_predict: int
    top_k: int


def _detect_ram_gb() -> int:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return max(1, round(kb / (1024 * 1024)))
    except Exception:
        return 8
    return 8


def _detect_cpu_threads() -> int:
    return max(1, int(os.cpu_count() or 4))


def detect_profile() -> TuningProfile:
    ram_gb = _detect_ram_gb()
    cpu_threads = _detect_cpu_threads()

    if ram_gb <= 8:
        return TuningProfile(
            name="low",
            ram_gb=ram_gb,
            cpu_threads=cpu_threads,
            model_candidates=["qwen2.5:1.5b", "qwen2.5:3b"],
            num_ctx=1536,
            num_predict=320,
            top_k=3,
        )

    if ram_gb <= 16:
        return TuningProfile(
            name="medium",
            ram_gb=ram_gb,
            cpu_threads=cpu_threads,
            model_candidates=["qwen2.5:3b", "llama3.2:3b", "mistral:7b"],
            num_ctx=2048,
            num_predict=384,
            top_k=4,
        )

    if ram_gb <= 24:
        return TuningProfile(
            name="balanced",
            ram_gb=ram_gb,
            cpu_threads=cpu_threads,
            model_candidates=["mistral:7b", "llama3.1:8b", "qwen2.5:7b"],
            num_ctx=3072,
            num_predict=512,
            top_k=4,
        )

    return TuningProfile(
        name="high",
        ram_gb=ram_gb,
        cpu_threads=cpu_threads,
        model_candidates=["mistral:7b", "qwen2.5:7b", "llama3.1:8b"],
        num_ctx=4096,
        num_predict=640,
        top_k=5,
    )
