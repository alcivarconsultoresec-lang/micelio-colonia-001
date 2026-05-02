import json
from datetime import datetime, timezone
from pathlib import Path


class ChatManager:
    """Local conversational interface for MICELIO.

    The chat answers from current local state first. If a local AI provider is
    available through LocalAIRouter, it can use it; otherwise it falls back to a
    deterministic operational response.
    """

    def __init__(self, repo_dir):
        self.repo_dir = Path(repo_dir)
        self.memory_dir = self.repo_dir / "memory"
        self.output_dir = self.repo_dir / "output"
        self.docs_data_dir = self.repo_dir / "docs" / "data"
        self.history_file = self.memory_dir / "chat_history.json"
        self.dashboard_file = self.docs_data_dir / "chat.json"
        for path in [self.memory_dir, self.output_dir, self.docs_data_dir]:
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

    def load_history(self):
        data = self.read_json(self.history_file, {"messages": []})
        data.setdefault("messages", [])
        return data

    def save_history(self, history):
        history["updated_at"] = self.now()
        self.write_json(self.history_file, history)
        self.write_json(self.dashboard_file, history)
        return history

    def context(self):
        return {
            "metrics": self.read_json(self.output_dir / "colony_metrics.json", {}),
            "construction": self.read_json(self.output_dir / "construction_options.json", {}),
            "mission": self.read_json(self.memory_dir / "evolution_mission.json", {}),
            "senses": self.read_json(self.output_dir / "senses_report.json", {}),
            "local_ai": self.read_json(self.output_dir / "local_ai_report.json", {}),
            "health": self.read_json(self.output_dir / "health_report.json", {}),
        }

    def fallback_answer(self, message, ctx):
        metrics = ctx.get("metrics", {}) if isinstance(ctx, dict) else {}
        construction = ctx.get("construction", {}) if isinstance(ctx, dict) else {}
        options = construction.get("options", []) if isinstance(construction, dict) else []
        pending = [x for x in options if x.get("status") == "pending"]
        approved = [x for x in options if x.get("status") == "approved"]
        applied = [x for x in options if x.get("status") == "applied"]
        lower = message.lower()

        if "constru" in lower or "herramient" in lower or "aprobar" in lower:
            if pending:
                first = pending[0]
                return (
                    f"Tengo {len(pending)} construcción(es) pendientes. La primera es: {first.get('title')}. "
                    f"Sirve para: {first.get('reasoning')}. Puedes aprobarla desde la sección Construcción aprobable."
                )
            if approved:
                first = approved[0]
                return f"Hay {len(approved)} construcción(es) aprobadas esperando aplicación. La primera es: {first.get('title')}. Toca Aplicar construcción."
            return f"No tengo construcciones pendientes. Ya hay {len(applied)} aplicadas. Presiona Generar sugerencias para producir nuevas opciones."

        if "estado" in lower or "ciclo" in lower or "evol" in lower:
            return (
                f"Estado actual: ciclo {metrics.get('cycle', '—')}, generación {metrics.get('generation', '—')}, "
                f"best score {metrics.get('best_score', '—')}, modo {metrics.get('mode', '—')}. "
                "La colonia mantiene selección, roles, tejidos y construcción aprobable."
            )

        if "ia" in lower or "ollama" in lower or "modelo" in lower:
            local_ai = ctx.get("local_ai", {})
            return (
                f"Router IA local: éxito={local_ai.get('success')}, proveedor={local_ai.get('selected_provider')}, "
                f"modelo={local_ai.get('selected_model')}. Si sigue en fallback, ejecuta scripts/termux_ai_probe.sh."
            )

        return (
            "Estoy operativo como centro local de MICELIO. Puedo explicarte estado, construcciones pendientes, IA local, linajes y próximos pasos. "
            "Pregunta por 'construcciones', 'estado evolutivo' o 'IA local'."
        )

    def ask(self, message):
        message = str(message or "").strip()
        if not message:
            return {"ok": False, "error": "empty_message"}
        history = self.load_history()
        ctx = self.context()
        user_item = {"role": "user", "content": message, "timestamp_utc": self.now()}
        history["messages"].append(user_item)

        answer = None
        provider = "local_state_fallback"
        try:
            from micelio.local_ai_router import LocalAIRouter
            prompt = (
                "Eres MICELIO, un organismo local controlado por su administrador. "
                "Responde en español, corto y operativo. No inventes capacidades.\n\n"
                f"Contexto JSON: {json.dumps(ctx, ensure_ascii=False)[:6000]}\n\n"
                f"Mensaje del administrador: {message}"
            )
            result = LocalAIRouter(self.repo_dir).generate(prompt, {"estrategia": {"temperatura": 0.35}})
            answer = result.get("texto") or self.fallback_answer(message, ctx)
            provider = result.get("modo", "local_ai")
        except Exception:
            answer = self.fallback_answer(message, ctx)

        assistant_item = {"role": "micelio", "content": answer, "timestamp_utc": self.now(), "provider": provider}
        history["messages"].append(assistant_item)
        history["messages"] = history["messages"][-80:]
        self.save_history(history)
        return {"ok": True, "answer": assistant_item, "history": history, "context": ctx}

    def clear(self):
        history = {"messages": [], "updated_at": self.now(), "cleared_at": self.now()}
        self.save_history(history)
        return {"ok": True, "history": history}
