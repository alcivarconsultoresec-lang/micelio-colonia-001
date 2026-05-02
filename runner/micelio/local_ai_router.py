import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

import requests


DEFAULT_OLLAMA_URL = os.getenv("MICELIO_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_OPENAI_LOCAL_URL = os.getenv("MICELIO_OPENAI_LOCAL_URL", "http://127.0.0.1:5001/v1/chat/completions")
DEFAULT_LOCAL_MODEL = os.getenv("MICELIO_LOCAL_MODEL", "")
DEFAULT_GITHUB_MODELS_ENDPOINT = os.getenv(
    "GITHUB_MODELS_ENDPOINT",
    "https://models.github.ai/inference/chat/completions",
)
DEFAULT_GITHUB_MODEL = os.getenv("MICELIO_MODEL", "openai/gpt-4o-mini")

PREFERRED_OLLAMA_MODELS = [
    "llama3.2:1b",
    "llama3.2",
    "qwen2.5:1.5b",
    "qwen2.5:0.5b",
    "gemma2:2b",
    "phi3:mini",
    "deepseek-r1:1.5b",
]


class LocalAIRouter:
    """AI provider router for MICELIO.

    Priority:
    1. Ollama local on 127.0.0.1:11434.
    2. OpenAI-compatible local endpoint on 127.0.0.1:5001.
    3. GitHub Models if the administrator provides a token.

    Secrets are read from environment variables or memory/secrets.local.json.
    That file is intentionally ignored by git.
    """

    def __init__(self, repo_dir):
        self.repo_dir = Path(repo_dir)
        self.output_dir = self.repo_dir / "output"
        self.dashboard_data_dir = self.repo_dir / "docs" / "data"
        self.memory_dir = self.repo_dir / "memory"
        self.secrets_file = self.memory_dir / "secrets.local.json"
        self.report_file = self.output_dir / "local_ai_report.json"
        self.dashboard_file = self.dashboard_data_dir / "local_ai.json"
        for path in [self.output_dir, self.dashboard_data_dir, self.memory_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def now(self):
        return datetime.now(timezone.utc).isoformat()

    def read_json(self, path, default):
        try:
            path = Path(path)
            if not path.exists():
                return default
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            return {"error": str(error), "default": default}

    def write_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def secrets(self):
        data = self.read_json(self.secrets_file, {})
        return data if isinstance(data, dict) else {}

    def secret(self, key, env_names=None, default=""):
        for name in env_names or []:
            value = os.getenv(name)
            if value:
                return value
        return self.secrets().get(key) or default

    def port_open(self, host, port, timeout=0.4):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def ollama_available(self):
        return self.port_open("127.0.0.1", 11434)

    def list_ollama_models(self):
        if not self.ollama_available():
            return []
        try:
            response = requests.get(f"{DEFAULT_OLLAMA_URL}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            return [item.get("name") for item in data.get("models", []) if item.get("name")]
        except Exception:
            return []

    def choose_ollama_model(self, models):
        preferred_model = self.secret("local_model", ["MICELIO_LOCAL_MODEL"], DEFAULT_LOCAL_MODEL)
        if preferred_model and preferred_model in models:
            return preferred_model
        if preferred_model:
            return preferred_model
        for preferred in PREFERRED_OLLAMA_MODELS:
            if preferred in models:
                return preferred
        return models[0] if models else None

    def generate_with_ollama(self, prompt, genoma):
        models = self.list_ollama_models()
        model = self.choose_ollama_model(models)
        if not model:
            raise RuntimeError("Ollama está disponible, pero no se detectaron modelos instalados.")
        estrategia = genoma.get("estrategia", {})
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(estrategia.get("temperatura", 0.7) or 0.7),
                "num_predict": int(os.getenv("MICELIO_LOCAL_MAX_TOKENS", self.secret("max_tokens", [], "350"))),
            },
        }
        response = requests.post(f"{DEFAULT_OLLAMA_URL}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return {
            "texto": data.get("response", "").strip(),
            "fitness": 0.82,
            "modo": "local_ai_ollama",
            "modelo": model,
            "provider": "ollama",
            "usage": {
                "eval_count": data.get("eval_count"),
                "prompt_eval_count": data.get("prompt_eval_count"),
                "total_duration": data.get("total_duration"),
            },
        }

    def generate_with_openai_local(self, prompt, genoma):
        if not self.port_open("127.0.0.1", 5001):
            raise RuntimeError("No se detectó endpoint local OpenAI-compatible en 127.0.0.1:5001.")
        estrategia = genoma.get("estrategia", {})
        model = self.secret("local_model", ["MICELIO_LOCAL_MODEL"], DEFAULT_LOCAL_MODEL) or "local-model"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Eres el núcleo local de MICELIO. Responde en español de forma operativa."},
                {"role": "user", "content": prompt},
            ],
            "temperature": float(estrategia.get("temperatura", 0.7) or 0.7),
            "max_tokens": int(os.getenv("MICELIO_LOCAL_MAX_TOKENS", self.secret("max_tokens", [], "350"))),
        }
        response = requests.post(DEFAULT_OPENAI_LOCAL_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return {
            "texto": data.get("choices", [{}])[0].get("message", {}).get("content", "").strip(),
            "fitness": 0.80,
            "modo": "local_ai_openai_compatible",
            "modelo": payload["model"],
            "provider": "openai_compatible_local",
            "usage": data.get("usage", {}),
        }

    def generate_with_github_models(self, prompt, genoma):
        token = self.secret("github_token", ["GITHUB_TOKEN", "MICELIO_GITHUB_TOKEN"])
        if not token:
            raise RuntimeError("No hay token de GitHub Models configurado.")
        estrategia = genoma.get("estrategia", {})
        model = self.secret("github_model", ["MICELIO_MODEL"], DEFAULT_GITHUB_MODEL)
        endpoint = self.secret("github_models_endpoint", ["GITHUB_MODELS_ENDPOINT"], DEFAULT_GITHUB_MODELS_ENDPOINT)
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres MICELIO, un organismo de software local administrado por su dueño. "
                        "Responde en español con diagnóstico, razonamiento operativo y acción concreta."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": float(estrategia.get("temperatura", 0.35) or 0.35),
            "max_tokens": int(os.getenv("MICELIO_LOCAL_MAX_TOKENS", self.secret("max_tokens", [], "700"))),
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = requests.post(endpoint, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return {
            "texto": data.get("choices", [{}])[0].get("message", {}).get("content", "").strip(),
            "fitness": 0.88,
            "modo": "remote_ai_github_models",
            "modelo": model,
            "provider": "github_models",
            "usage": data.get("usage", {}),
        }

    def provider_status(self):
        secrets = self.secrets()
        token = self.secret("github_token", ["GITHUB_TOKEN", "MICELIO_GITHUB_TOKEN"])
        return {
            "ollama_available": self.ollama_available(),
            "ollama_models": self.list_ollama_models() if self.ollama_available() else [],
            "openai_local_5001": self.port_open("127.0.0.1", 5001),
            "github_token_configured": bool(token),
            "github_model": self.secret("github_model", ["MICELIO_MODEL"], DEFAULT_GITHUB_MODEL),
            "secrets_file_exists": self.secrets_file.exists(),
            "secret_keys": sorted([k for k in secrets.keys() if "token" not in k.lower()]),
        }

    def generate(self, prompt, genoma):
        attempts = []
        if os.getenv("MICELIO_DISABLE_LOCAL_AI", "false") == "true":
            raise RuntimeError("MICELIO_DISABLE_LOCAL_AI=true; router IA deshabilitado por configuración.")

        for provider, fn in [
            ("ollama", self.generate_with_ollama),
            ("openai_compatible_local", self.generate_with_openai_local),
            ("github_models", self.generate_with_github_models),
        ]:
            try:
                result = fn(prompt, genoma)
                self.write_report(True, result, attempts)
                return result
            except Exception as error:
                attempts.append({"provider": provider, "error": str(error)})

        self.write_report(False, None, attempts)
        raise RuntimeError("No hay proveedor de IA disponible para MICELIO.")

    def write_report(self, success, result, attempts):
        report = {
            "timestamp_utc": self.now(),
            "phase": "fase_4_router_ia_hibrida",
            "success": success,
            "selected_provider": result.get("provider") if result else None,
            "selected_model": result.get("modelo") if result else None,
            "provider_status": self.provider_status(),
            "attempts": attempts,
            "safety": "Se usan proveedores locales o token configurado explícitamente por el administrador.",
        }
        self.write_json(self.report_file, report)
        self.write_json(self.dashboard_file, report)
        return report
