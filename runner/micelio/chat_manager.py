import json
from datetime import datetime, timezone
from pathlib import Path


class ChatManager:
    """Chat local contextual para MICELIO.

    Si no hay LLM local conectado, responde con diagnóstico estructurado usando
    el estado real del sistema, no una plantilla genérica fija.
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
            "registry": self.read_json(self.memory_dir / "tool_registry.json", {}),
            "mission": self.read_json(self.memory_dir / "evolution_mission.json", {}),
            "senses": self.read_json(self.output_dir / "senses_report.json", {}),
            "local_ai": self.read_json(self.output_dir / "local_ai_report.json", {}),
            "health": self.read_json(self.output_dir / "health_report.json", {}),
            "chat_personality": self.read_json(self.memory_dir / "chat_personality.json", {}),
        }

    def summarize_construction(self, ctx):
        construction = ctx.get("construction", {}) if isinstance(ctx, dict) else {}
        options = construction.get("options", []) if isinstance(construction, dict) else []
        registry = ctx.get("registry", {}) if isinstance(ctx, dict) else {}
        tools = registry.get("tools", {}) if isinstance(registry, dict) else {}
        pending = [x for x in options if x.get("status") == "pending"]
        approved = [x for x in options if x.get("status") == "approved"]
        verified = [x for x in options if x.get("status") == "verified"]
        unverified = [x for x in options if x.get("status") == "applied_unverified"]
        return pending, approved, verified, unverified, tools

    def structured_answer(self, message, ctx):
        metrics = ctx.get("metrics", {}) if isinstance(ctx, dict) else {}
        local_ai = ctx.get("local_ai", {}) if isinstance(ctx, dict) else {}
        senses = ctx.get("senses", {}) if isinstance(ctx, dict) else {}
        pending, approved, verified, unverified, tools = self.summarize_construction(ctx)
        lower = message.lower().strip()

        if lower in {"hola", "buenas", "hello", "hey"}:
            return (
                f"Hola. Estoy activo en ciclo {metrics.get('cycle', '—')} y generación {metrics.get('generation', '—')}.\n"
                f"Herramientas verificadas: {len(tools)}. Pendientes: {len(pending)}. Aprobadas sin aplicar: {len(approved)}.\n"
                f"IA actual: {local_ai.get('selected_provider') or 'sin proveedor local'}; modo probable: {metrics.get('mode', '—')}.\n"
                "Pregunta: 'qué construir ahora', 'diagnóstico', 'IA local' o 'evolución tecnológica'."
            )

        if any(word in lower for word in ["diagn", "problema", "fall", "plantilla", "genérico"]):
            hypothesis = []
            if not local_ai.get("success"):
                hypothesis.append("el chat está usando respuesta contextual local porque no hay IA local activa")
            if not tools:
                hypothesis.append("aún no hay registro consolidado de herramientas verificadas")
            if unverified:
                hypothesis.append(f"hay {len(unverified)} construcción(es) aplicadas pero no verificadas")
            if not hypothesis:
                hypothesis.append("el sistema está respondiendo con estado local; falta conectar un modelo para razonamiento abierto")
            return (
                "Diagnóstico:\n- " + "\n- ".join(hypothesis) + "\n\n"
                "Acción recomendada:\n"
                "1. Ejecuta una construcción de 'Mejorar razonamiento local del chat'.\n"
                "2. Ejecuta scripts/termux_ai_probe.sh para saber si existe IA local.\n"
                "3. Revisa el registro de herramientas verificadas antes de generar más sugerencias."
            )

        if any(word in lower for word in ["constru", "herramient", "aprobar", "suger"]):
            if approved:
                item = approved[0]
                return f"Hay una construcción aprobada esperando aplicación: {item.get('title')}. Aplícala y luego verifica el estado."
            if pending:
                ranked = sorted(pending, key=lambda x: (x.get("wave", 9), 0 if x.get("priority") == "alta" else 1))
                item = ranked[0]
                return (
                    f"Recomiendo construir ahora: {item.get('title')}.\n"
                    f"Motivo: {item.get('reasoning')}\n"
                    f"Archivos esperados: {', '.join(item.get('expected_files', []))}.\n"
                    "Aprobación: usa el botón Aprobar y luego Aplicar construcción."
                )
            return "No veo construcciones pendientes. Toca Generar sugerencias; el gestor ya evita repetir herramientas verificadas."

        if any(word in lower for word in ["evol", "estado", "ciclo", "score"]):
            return (
                f"Estado evolutivo:\n"
                f"- Ciclo: {metrics.get('cycle', '—')}\n"
                f"- Generación: {metrics.get('generation', '—')}\n"
                f"- Best score: {metrics.get('best_score', '—')}\n"
                f"- Average score: {metrics.get('average_score', '—')}\n"
                f"- Presión: {metrics.get('selection_pressure', '—')}\n"
                f"- Herramientas verificadas: {len(tools)}\n"
                "La evolución genética existe; la evolución tecnológica depende de construcciones verificadas en el registro."
            )

        if any(word in lower for word in ["ia", "ollama", "modelo", "inteligencia"]):
            ollama = (senses.get("local_ai", {}) or {}).get("ollama", {}) if isinstance(senses, dict) else {}
            return (
                f"IA local:\n"
                f"- Router success: {local_ai.get('success')}\n"
                f"- Proveedor: {local_ai.get('selected_provider')}\n"
                f"- Modelo: {local_ai.get('selected_model')}\n"
                f"- Ollama binario: {ollama.get('binary_available')}\n"
                f"- Modelos detectados: {ollama.get('models', [])}\n"
                "Si todo sale vacío, el chat no está usando LLM: está usando diagnóstico local."
            )

        return (
            f"Entendido. Lo leo desde mi estado local: ciclo {metrics.get('cycle', '—')}, generación {metrics.get('generation', '—')}, "
            f"herramientas verificadas {len(tools)}, pendientes {len(pending)}. "
            "Puedo responder mejor si me preguntas por diagnóstico, construcción, IA local o evolución tecnológica."
        )

    def ask(self, message):
        message = str(message or "").strip()
        if not message:
            return {"ok": False, "error": "empty_message"}
        history = self.load_history()
        ctx = self.context()
        history["messages"].append({"role": "user", "content": message, "timestamp_utc": self.now()})
        provider = "local_state_reasoner"
        try:
            from micelio.local_ai_router import LocalAIRouter
            prompt = (
                "Eres MICELIO, sistema local de administración. Responde en español con diagnóstico, hipótesis y acción.\n"
                f"Contexto: {json.dumps(ctx, ensure_ascii=False)[:8000]}\n"
                f"Mensaje: {message}"
            )
            result = LocalAIRouter(self.repo_dir).generate(prompt, {"estrategia": {"temperatura": 0.35}})
            answer = result.get("texto") or self.structured_answer(message, ctx)
            provider = result.get("modo", "local_ai")
        except Exception:
            answer = self.structured_answer(message, ctx)
        item = {"role": "micelio", "content": answer, "timestamp_utc": self.now(), "provider": provider}
        history["messages"].append(item)
        history["messages"] = history["messages"][-80:]
        self.save_history(history)
        return {"ok": True, "answer": item, "history": history, "context": ctx}

    def clear(self):
        history = {"messages": [], "updated_at": self.now(), "cleared_at": self.now()}
        self.save_history(history)
        return {"ok": True, "history": history}
