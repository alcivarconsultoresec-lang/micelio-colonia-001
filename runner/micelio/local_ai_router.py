import json
import os
import socket
from datetime import datetime, timezone

import requests


DEFAULT_OLLAMA_URL = os.getenv("MICELIO_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_OPENAI_LOCAL_URL = os.getenv("MICELIO_OPENAI_LOCAL_URL", "http://127.0.0.1:5001/v1/chat/completions")
DEFAULT_LOCAL_MODEL = os.getenv("MICELIO_LOCAL_MODEL", "")

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
    """Local AI provider router for authorized Termux/Android environments.

    The router only connects to local loopback services or explicit URLs set by
    the user. It does not download models, start background daemons, or contact
    external providers without configuration.
    """

    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.output_dir = os.path.join(repo_dir, "output")
        self.dashboard_data_dir = os.path.join(repo_dir, "docs", "data")
        self.report_file = os.path.join(self.output_dir, "local_ai_report.json")
        self.dashboard_file = os.path.join(self.dashboard_data_dir, "local_ai.json")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.dashboard_data_dir, exist_ok=True)

    def now(self):
        return datetime.now(timezone.utc).isoformat()

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")

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
        if DEFAULT_LOCAL_MODEL and DEFAULT_LOCAL_MODEL in models:
            return DEFAULT_LOCAL_MODEL
        if DEFAULT_LOCAL_MODEL:
            return DEFAULT_LOCAL_MODEL
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
                "num_predict": int(os.getenv("MICELIO_LOCAL_MAX_TOKENS", "350")),
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
        payload = {
            "model": DEFAULT_LOCAL_MODEL or "local-model",
            "messages": [
                {"role": "system", "content": "Eres el núcleo local de MICELIO. Responde en español de forma operativa."},
                {"role": "user", "content": prompt},
            ],
            "temperature": float(estrategia.get("temperatura", 0.7) or 0.7),
            "max_tokens": int(os.getenv("MICELIO_LOCAL_MAX_TOKENS", "350")),
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

    def generate(self, prompt, genoma):
        attempts = []
        if os.getenv("MICELIO_DISABLE_LOCAL_AI", "false") == "true":
            raise RuntimeError("MICELIO_DISABLE_LOCAL_AI=true; router local deshabilitado por configuración.")

        try:
            result = self.generate_with_ollama(prompt, genoma)
            self.write_report(True, result, attempts)
            return result
        except Exception as error:
            attempts.append({"provider": "ollama", "error": str(error)})

        try:
            result = self.generate_with_openai_local(prompt, genoma)
            self.write_report(True, result, attempts)
            return result
        except Exception as error:
            attempts.append({"provider": "openai_compatible_local", "error": str(error)})

        self.write_report(False, None, attempts)
        raise RuntimeError("No hay IA local disponible para MICELIO.")

    def write_report(self, success, result, attempts):
        report = {
            "timestamp_utc": self.now(),
            "phase": "fase_3_router_ia_local",
            "success": success,
            "selected_provider": result.get("provider") if result else None,
            "selected_model": result.get("modelo") if result else None,
            "ollama_available": self.ollama_available(),
            "ollama_models": self.list_ollama_models() if self.ollama_available() else [],
            "attempts": attempts,
            "safety": "Solo se usan endpoints locales o explícitamente configurados por el usuario.",
        }
        self.write_json(self.report_file, report)
        self.write_json(self.dashboard_file, report)
        return report
