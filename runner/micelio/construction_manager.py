import json
from datetime import datetime, timezone
from pathlib import Path


class ConstructionManager:
    """Supervised construction/approval layer for MICELIO.

    Converts reasoning into concrete construction options and applies only
    allowlisted local patches after explicit administrator approval.
    """

    def __init__(self, repo_dir):
        self.repo_dir = Path(repo_dir)
        self.memory_dir = self.repo_dir / "memory"
        self.output_dir = self.repo_dir / "output"
        self.docs_data_dir = self.repo_dir / "docs" / "data"
        self.queue_file = self.memory_dir / "build_queue.json"
        self.report_file = self.output_dir / "construction_options.json"
        self.dashboard_file = self.docs_data_dir / "construction_options.json"
        self.allowed_types = {
            "lineage_view": self.apply_lineage_view,
            "health_monitor": self.apply_health_monitor,
            "mission_manifest": self.apply_mission_manifest,
            "termux_ai_probe": self.apply_termux_ai_probe,
            "organism_dashboard_upgrade": self.apply_organism_dashboard_upgrade,
            "chat_window": self.apply_chat_window,
            "gitignore_cleanup": self.apply_gitignore_cleanup,
        }
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

    def load_queue(self):
        queue = self.read_json(self.queue_file, {"options": [], "history": []})
        queue.setdefault("options", [])
        queue.setdefault("history", [])
        return queue

    def save_queue(self, queue):
        queue["updated_at"] = self.now()
        self.write_json(self.queue_file, queue)
        self.write_json(self.report_file, queue)
        self.write_json(self.dashboard_file, queue)
        return queue

    def option_exists(self, queue, option_id):
        return any(item.get("id") == option_id and item.get("status") in {"pending", "approved", "applied"} for item in queue.get("options", []))

    def build_option(self, option_id, title, type_name, priority, reason, expected_files):
        return {
            "id": option_id,
            "title": title,
            "type": type_name,
            "priority": priority,
            "status": "pending",
            "created_at": self.now(),
            "approval_mode": "manual_admin_dashboard",
            "question": "¿Quieres que construya esto?",
            "reasoning": reason,
            "expected_files": expected_files,
            "risk_level": "controlled_local_write",
            "apply_method": "allowlisted_patch",
        }

    def generate_options(self, force=False):
        queue = self.load_queue()
        metrics = self.read_json(self.output_dir / "colony_metrics.json", {})
        tissues = self.read_json(self.output_dir / "tissues_report.json", {})
        local_ai = self.read_json(self.output_dir / "local_ai_report.json", {})
        autocoder = self.read_json(self.output_dir / "autocoder_plan.json", {})

        candidates = [
            self.build_option("build_lineage_view", "Construir vista de linaje dominante", "lineage_view", "alta", "La colonia ya tiene generaciones activas. Necesita visualizar padres, ramas, scores y familias dominantes para decidir qué linajes activar.", ["docs/lineage.html"]),
            self.build_option("build_health_monitor", "Crear órgano de salud y homeostasis", "health_monitor", "alta", "El sistema genera ciclos, reportes y commits. Necesita evaluar memoria, disco, presión evolutiva y señales de saturación.", ["runner/micelio/health_monitor.py", "output/health_report.json", "docs/data/health.json"]),
            self.build_option("build_mission_manifest", "Definir propósito evolutivo operativo", "mission_manifest", "alta", "El organismo necesita propósito explícito además de mecanismos: misión, objetivos de evolución, límites, criterios de éxito y próximos órganos.", ["memory/evolution_mission.json", "docs/data/mission.json"]),
            self.build_option("build_termux_ai_probe", "Construir herramienta de detección IA local", "termux_ai_probe", "media", "Los reportes indican modo local_fallback. Se necesita una herramienta rápida para verificar Ollama, puertos locales, modelos y recomendaciones manuales.", ["scripts/termux_ai_probe.sh"]),
            self.build_option("build_organism_dashboard_upgrade", "Mejorar mapa del organismo con decisiones aprobables", "organism_dashboard_upgrade", "media", "El mapa debe mostrar no solo órganos, sino también decisiones de construcción y próximos pasos aprobables por el administrador.", ["docs/data/organism_upgrade.json"]),
            self.build_option("build_chat_window", "Agregar ventana de chat directa con MICELIO", "chat_window", "alta", "El administrador necesita conversar directamente con el organismo para preguntarle estado, próximas construcciones, IA local y decisiones evolutivas.", ["runner/micelio/chat_manager.py", "memory/chat_history.json", "docs/data/chat.json"]),
            self.build_option("build_gitignore_cleanup", "Limpiar commits de archivos generados", "gitignore_cleanup", "media", "Los commits empezaron a incluir __pycache__ y archivos temporales. Se necesita .gitignore para evitar ruido y mantener el repositorio sano.", [".gitignore"]),
        ]

        added = []
        if force:
            active_ids = {item["id"] for item in candidates}
            for item in queue.get("options", []):
                if item.get("id") in active_ids and item.get("status") in {"rejected"}:
                    item["status"] = "pending"
                    item["reopened_at"] = self.now()
                    added.append(item.get("id"))
        for item in candidates:
            if not self.option_exists(queue, item["id"]):
                queue["options"].append(item)
                added.append(item["id"])

        queue["last_generation_context"] = {
            "timestamp_utc": self.now(),
            "cycle": metrics.get("cycle"),
            "generation": metrics.get("generation"),
            "mode": metrics.get("mode"),
            "best_score": metrics.get("best_score"),
            "local_ai_success": local_ai.get("success"),
            "local_ai_provider": local_ai.get("selected_provider"),
            "tissues_count": len(tissues.get("tissues", [])) if isinstance(tissues, dict) else 0,
            "autocoder_tasks": len(autocoder.get("tasks", [])) if isinstance(autocoder, dict) else 0,
            "added_options": added,
        }
        queue["last_generate_message"] = "Nuevas sugerencias agregadas." if added else "No hay sugerencias nuevas; las existentes ya están pendientes, aprobadas o aplicadas. Usa Limpiar cola para archivar aplicadas."
        return self.save_queue(queue)

    def clear_queue(self, mode="archive_applied"):
        queue = self.load_queue()
        history = queue.get("history", [])
        old_options = queue.get("options", [])
        if mode == "all":
            archived = old_options
            remaining = []
        else:
            archived = [item for item in old_options if item.get("status") in {"applied", "rejected"}]
            remaining = [item for item in old_options if item.get("status") not in {"applied", "rejected"}]
        history.append({"timestamp_utc": self.now(), "action": "clear_queue", "mode": mode, "archived_count": len(archived)})
        queue["options"] = remaining
        queue["archived_options"] = (queue.get("archived_options", []) + archived)[-100:]
        queue["history"] = history
        queue["last_generate_message"] = f"Cola limpiada. Archivadas: {len(archived)}. Activas: {len(remaining)}."
        return self.save_queue(queue)

    def find_option(self, queue, option_id):
        for item in queue.get("options", []):
            if item.get("id") == option_id:
                return item
        return None

    def approve(self, option_id):
        queue = self.load_queue()
        item = self.find_option(queue, option_id)
        if not item:
            return {"ok": False, "error": "option_not_found"}
        if item.get("status") == "applied":
            return {"ok": True, "option": item, "message": "already_applied"}
        item["status"] = "approved"
        item["approved_at"] = self.now()
        queue["history"].append({"timestamp_utc": self.now(), "action": "approved", "option_id": option_id})
        self.save_queue(queue)
        return {"ok": True, "option": item}

    def reject(self, option_id):
        queue = self.load_queue()
        item = self.find_option(queue, option_id)
        if not item:
            return {"ok": False, "error": "option_not_found"}
        item["status"] = "rejected"
        item["rejected_at"] = self.now()
        queue["history"].append({"timestamp_utc": self.now(), "action": "rejected", "option_id": option_id})
        self.save_queue(queue)
        return {"ok": True, "option": item}

    def apply(self, option_id):
        queue = self.load_queue()
        item = self.find_option(queue, option_id)
        if not item:
            return {"ok": False, "error": "option_not_found"}
        if item.get("status") != "approved":
            return {"ok": False, "error": "option_not_approved", "status": item.get("status")}
        handler = self.allowed_types.get(item.get("type"))
        if not handler:
            return {"ok": False, "error": "type_not_allowlisted", "type": item.get("type")}
        result = handler()
        item["status"] = "applied"
        item["applied_at"] = self.now()
        item["result"] = result
        queue["history"].append({"timestamp_utc": self.now(), "action": "applied", "option_id": option_id, "result": result})
        self.save_queue(queue)
        return {"ok": True, "option": item, "result": result}

    def apply_lineage_view(self):
        content = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MICELIO Linaje</title><style>body{margin:0;background:#050816;color:#f7f9ff;font-family:system-ui;padding:14px 14px 80px}.card{background:#0d1730;border:1px solid #8aa4ff33;border-radius:20px;padding:14px;margin:10px 0}.node{background:#14203d;border-radius:14px;padding:10px;margin:8px 0}.muted{color:#9aa8c7;font-size:13px}.bar{height:10px;background:#ffffff14;border-radius:99px;overflow:hidden}.bar div{height:100%;background:linear-gradient(90deg,#55e6ff,#67ffb1)}a{color:#55e6ff}</style></head><body><h1>MICELIO · Linaje</h1><p class="muted">Ramas dominantes, padres y scores.</p><a href="/control.html">Volver al control</a><section class="card"><h2>Linajes elite</h2><div id="lineage">Cargando...</div></section><script>async function load(){const r=await fetch('/api/status');const s=await r.json();const top=s.metrics?.top_role_spores||[];document.getElementById('lineage').innerHTML=top.map(x=>`<div class="node"><b>${x.spore_id}</b><p class="muted">Padre: ${x.parent_id||'root'} · Rol: ${x.role||'—'} · Gen: ${x.generation||'—'}</p><div class="bar"><div style="width:${Math.max(0,Math.min(100,(x.adjusted_score||x.selection_score||0)*100))}%"></div></div><p class="muted">Score: ${(x.adjusted_score||x.selection_score||0).toFixed(4)}</p></div>`).join('')||'Sin linajes todavía.'}load();setInterval(load,3000)</script></body></html>'''
        path = self.repo_dir / "docs" / "lineage.html"
        path.write_text(content, encoding="utf-8")
        return {"files_written": ["docs/lineage.html"]}

    def apply_health_monitor(self):
        content = '''import json\nimport os\nimport shutil\nfrom datetime import datetime, timezone\n\n\ndef now():\n    return datetime.now(timezone.utc).isoformat()\n\n\ndef build_health(repo_dir):\n    output = os.path.join(repo_dir, "output")\n    data = os.path.join(repo_dir, "docs", "data")\n    os.makedirs(output, exist_ok=True)\n    os.makedirs(data, exist_ok=True)\n    usage = shutil.disk_usage(repo_dir)\n    metrics_path = os.path.join(output, "colony_metrics.json")\n    metrics = {}\n    if os.path.exists(metrics_path):\n        with open(metrics_path, "r", encoding="utf-8") as file:\n            metrics = json.load(file)\n    health = {\n        "timestamp_utc": now(),\n        "disk_free_mb": round(usage.free / 1024 / 1024, 2),\n        "disk_used_mb": round(usage.used / 1024 / 1024, 2),\n        "cycle": metrics.get("cycle"),\n        "generation": metrics.get("generation"),\n        "selection_pressure": metrics.get("selection_pressure"),\n        "status": "healthy" if usage.free > 200 * 1024 * 1024 else "low_disk",\n    }\n    for path in [os.path.join(output, "health_report.json"), os.path.join(data, "health.json")]:\n        with open(path, "w", encoding="utf-8") as file:\n            json.dump(health, file, indent=2, ensure_ascii=False)\n            file.write("\\n")\n    return health\n'''
        path = self.repo_dir / "runner" / "micelio" / "health_monitor.py"
        path.write_text(content, encoding="utf-8")
        return {"files_written": ["runner/micelio/health_monitor.py"]}

    def apply_mission_manifest(self):
        mission = {
            "timestamp_utc": self.now(),
            "mission": "evolucionar_como_organismo_local_controlado",
            "purpose": "aprender del entorno Termux/Android, construir herramientas internas aprobadas y mejorar la arquitectura de la colonia",
            "strategic_objectives": ["aumentar_capacidad_sensorial_local", "mejorar_razonamiento_con_ia_local_o_remota_autorizada", "formar_organos_virtuales_mas_utiles", "proponer_autocodificacion_aprobable", "mantener_homeostasis_de_recursos"],
            "success_metrics": ["generacion_creciente", "score_promedio_creciente", "opciones_de_construccion_aplicadas", "reduccion_de_fallback_por_uso_de_ia_local", "salud_de_recursos_estable"],
            "control": "administrador_aprueba_construcciones_desde_dashboard",
        }
        self.write_json(self.memory_dir / "evolution_mission.json", mission)
        self.write_json(self.docs_data_dir / "mission.json", mission)
        return {"files_written": ["memory/evolution_mission.json", "docs/data/mission.json"]}

    def apply_termux_ai_probe(self):
        content = '''#!/data/data/com.termux/files/usr/bin/bash\nset -euo pipefail\necho "[MICELIO] Diagnóstico IA local"\ncommand -v ollama >/dev/null 2>&1 && echo "ollama: instalado" || echo "ollama: no instalado"\npython - <<'PY'\nimport socket\nfor name, port in [("ollama",11434),("openai-compatible",5001),("llama-cpp",8081)]:\n    s=socket.socket(); s.settimeout(.5)\n    try:\n        s.connect(("127.0.0.1",port)); print(f"{name}: puerto {port} abierto")\n    except Exception:\n        print(f"{name}: puerto {port} cerrado")\n    finally:\n        s.close()\nPY\nif command -v ollama >/dev/null 2>&1; then ollama list || true; fi\n'''
        path = self.repo_dir / "scripts" / "termux_ai_probe.sh"
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
        return {"files_written": ["scripts/termux_ai_probe.sh"]}

    def apply_organism_dashboard_upgrade(self):
        marker = self.repo_dir / "docs" / "data" / "organism_upgrade.json"
        payload = {"timestamp_utc": self.now(), "upgrade": "organism_dashboard_decision_layer", "status": "applied_marker", "note": "El mapa del organismo puede consumir construction_options.json para mostrar decisiones aprobables."}
        self.write_json(marker, payload)
        return {"files_written": ["docs/data/organism_upgrade.json"]}

    def apply_chat_window(self):
        payload = {"timestamp_utc": self.now(), "chat_window": "available", "endpoint": "/api/chat", "history": "memory/chat_history.json"}
        self.write_json(self.docs_data_dir / "chat_window.json", payload)
        return {"files_written": ["docs/data/chat_window.json"]}

    def apply_gitignore_cleanup(self):
        path = self.repo_dir / ".gitignore"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        additions = ["__pycache__/", "*.pyc", ".pytest_cache/", "output/*.log", "*.tmp"]
        lines = existing.splitlines()
        for item in additions:
            if item not in lines:
                lines.append(item)
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return {"files_written": [".gitignore"], "note": "No borra historial, evita nuevos archivos temporales."}
