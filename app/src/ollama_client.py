import requests

from .config import settings


class OllamaClient:
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def _url(self, path: str) -> str:
        return f"{self.host}{path}"

    def ensure_model(self, auto_pull: bool = True) -> str:
        tags_resp = requests.get(self._url("/api/tags"), timeout=30)
        tags_resp.raise_for_status()
        models = tags_resp.json().get("models", [])
        names = {item.get("name", "") for item in models}

        if self.model == "auto":
            for candidate in settings.model_candidates:
                if candidate in names:
                    self.model = candidate
                    return self.model

            if not auto_pull:
                raise RuntimeError(
                    "No auto model candidate found in Ollama and auto-pull is disabled. "
                    f"Candidates: {settings.model_candidates}"
                )

            selected = settings.model_candidates[0]
            pull_resp = requests.post(
                self._url("/api/pull"),
                json={"name": selected, "stream": False},
                timeout=1800,
            )
            pull_resp.raise_for_status()
            self.model = selected
            return self.model

        if self.model in names:
            return self.model

        if not auto_pull:
            raise RuntimeError(f"Model '{self.model}' not found in Ollama and auto-pull is disabled.")

        pull_resp = requests.post(
            self._url("/api/pull"),
            json={"name": self.model, "stream": False},
            timeout=1800,
        )
        pull_resp.raise_for_status()
        return self.model

    def generate(self, prompt: str) -> str:
        resp = requests.post(
            self._url("/api/generate"),
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": settings.generation_temperature,
                    "num_ctx": settings.generation_num_ctx,
                    "num_predict": settings.generation_num_predict,
                    "num_thread": settings.generation_num_thread,
                },
            },
            timeout=240,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


ollama_client = OllamaClient(settings.ollama_host, settings.ollama_model)
