import json
from datetime import datetime, timezone
from pathlib import Path


class ConstructionManager:
    """Gestor de construcción aprobada por el administrador.

    Evita repetir sugerencias ya aplicadas y verifica los archivos resultantes.
    """

    def __init__(self, repo_dir):
        self.repo_dir = Path(repo_dir)
        self.memory_dir = self.repo_dir / "memory"
        self.output_dir = self.repo_dir / "output"
        self.docs_data_dir = self.repo_dir / "docs" / "data"
        self.queue_file = self.memory_dir / "build_queue.json"
        self.report_file = self.output_dir / "construction_options.json"
        self.dashboard_file = self.docs_data_dir / "construction_options.json"
        self.registry_file = self.memory_dir / "tool_registry.json"
        self.registry_dashboard_file = self.docs_data_dir / "tool_registry.json"
        self.allowed_types = {
            "lineage_view": self.apply_lineage_view,
            "health_monitor": self.apply_health_monitor,
            "mission_manifest": self.apply_mission_manifest,
            "termux_ai_probe": self.apply_termux_ai_probe,
            "organism_dashboard_upgrade": self.apply_organism_dashboard_upgrade,
            "chat_window": self.apply_chat_window,
            "gitignore_cleanup": self.apply_gitignore_cleanup,
            "construction_verifier": self.apply_construction_verifier,
            "health_dashboard": self.apply_health_dashboard,
            "evolution_changelog": self.apply_evolution_changelog,
            "chat_reasoning_upgrade": self.apply_chat_reasoning_upgrade,
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

    def verify_files(self, files):
        checked = []
        ok = 0
        for rel in files or []:
            path = self.repo_dir / rel
            exists = path.exists()
            ok += 1 if exists else 0
            checked.append({
                "path": rel,
                "exists": exists,
                "size_bytes": path.stat().st_size if exists and path.is_file() else None,
                "kind": "directory" if exists and path.is_dir() else "file" if exists else "missing",
            })
        return {
            "verified_at": self.now(),
            "ok": bool(files) and ok == len(files),
            "expected_count": len(files or []),
            "existing_count": ok,
            "files": checked,
        }

    def load_queue(self):
        queue = self.read_json(self.queue_file, {"options": [], "history": [], "archived_options": []})
        queue.setdefault("options", [])
        queue.setdefault("history", [])
        queue.setdefault("archived_options", [])
        return queue

    def save_queue(self, queue):
        queue["updated_at"] = self.now()
        self.write_json(self.queue_file, queue)
        self.write_json(self.report_file, queue)
        self.write_json(self.dashboard_file, queue)
        return queue

    def load_registry(self):
        registry = self.read_json(self.registry_file, {"tools": {}, "history": []})
        registry.setdefault("tools", {})
        registry.setdefault("history", [])
        return registry

    def save_registry(self, registry):
        registry["updated_at"] = self.now()
        self.write_json(self.registry_file, registry)
        self.write_json(self.registry_dashboard_file, registry)
        return registry

    def option(self, option_id, title, type_name, priority, reason, expected_files, wave):
        return {
            "id": option_id,
            "title": title,
            "type": type_name,
            "priority": priority,
            "wave": wave,
            "status": "pending",
            "created_at": self.now(),
            "question": "¿Quieres que construya esto?",
            "reasoning": reason,
            "expected_files": expected_files,
            "verification": self.verify_files(expected_files),
            "apply_method": "allowlisted_patch",
        }

    def templates(self):
        return [
            self.option("build_lineage_view", "Construir vista de linaje dominante", "lineage_view", "alta", "Visualiza padres, ramas, scores y familias dominantes.", ["docs/lineage.html"], 1),
            self.option("build_health_monitor", "Crear órgano de salud y homeostasis", "health_monitor", "alta", "Evalúa disco, generación y presión de selección.", ["runner/micelio/health_monitor.py"], 1),
            self.option("build_mission_manifest", "Definir propósito operativo", "mission_manifest", "alta", "Define misión, objetivos y métricas de éxito.", ["memory/evolution_mission.json", "docs/data/mission.json"], 1),
            self.option("build_termux_ai_probe", "Crear diagnóstico de IA local", "termux_ai_probe", "media", "Verifica Ollama, puertos locales y modelos disponibles.", ["scripts/termux_ai_probe.sh"], 1),
            self.option("build_organism_dashboard_upgrade", "Registrar mejora del mapa", "organism_dashboard_upgrade", "media", "Marca una mejora visible para el mapa del organismo.", ["docs/data/organism_upgrade.json"], 1),
            self.option("build_chat_window", "Activar ventana de chat directa", "chat_window", "alta", "Registra la capacidad de conversación local.", ["docs/data/chat_window.json"], 1),
            self.option("build_gitignore_cleanup", "Limpiar archivos generados", "gitignore_cleanup", "media", "Evita que pycache y temporales entren a futuros commits.", [".gitignore"], 1),
            self.option("build_construction_verifier", "Construir verificador de herramientas", "construction_verifier", "alta", "Comprueba si cada herramienta aprobada realmente escribió archivos.", ["runner/micelio/build_verifier.py", "docs/data/build_verifier.json"], 2),
            self.option("build_health_dashboard", "Construir panel visual de salud", "health_dashboard", "alta", "Muestra salud y recursos en una pantalla propia.", ["docs/health.html"], 2),
            self.option("build_evolution_changelog", "Construir bitácora tecnológica", "evolution_changelog", "media", "Muestra historial de aprobaciones, aplicaciones y verificaciones.", ["docs/evolution_log.html"], 2),
            self.option("build_chat_reasoning_upgrade", "Mejorar razonamiento local del chat", "chat_reasoning_upgrade", "alta", "Hace que el chat entregue diagnóstico, hipótesis y acción recomendada.", ["memory/chat_personality.json", "docs/data/chat_capabilities.json"], 2),
        ]

    def completed_ids(self, queue, registry):
        done = set(registry.get("tools", {}).keys())
        for bucket in [queue.get("options", []), queue.get("archived_options", [])]:
            for item in bucket:
                if item.get("status") in {"applied", "verified"} and self.verify_files(item.get("expected_files", [])).get("ok"):
                    done.add(item.get("id"))
        for item in self.templates():
            if self.verify_files(item.get("expected_files", [])).get("ok"):
                done.add(item["id"])
        return done

    def generate_options(self, force=False):
        queue = self.load_queue()
        registry = self.load_registry()
        active_ids = {x.get("id") for x in queue.get("options", []) if x.get("status") in {"pending", "approved"}}
        done = self.completed_ids(queue, registry)
        added = []
        for item in self.templates():
            if item["id"] in done:
                continue
            if item["id"] in active_ids:
                continue
            queue["options"].append(item)
            active_ids.add(item["id"])
            added.append(item["id"])
        queue["last_generation_context"] = {"timestamp_utc": self.now(), "added_options": added, "verified_tools_total": len(done)}
        queue["last_generate_message"] = "Nuevas sugerencias agregadas: " + ", ".join(added) if added else "No repetí sugerencias ya construidas. No hay nuevas opciones pendientes para esta oleada."
        return self.save_queue(queue)

    def clear_queue(self, mode="archive_applied"):
        queue = self.load_queue()
        old = queue.get("options", [])
        if mode == "all":
            archived, remaining = old, []
        else:
            archived = [x for x in old if x.get("status") in {"applied", "verified", "rejected"}]
            remaining = [x for x in old if x.get("status") not in {"applied", "verified", "rejected"}]
        queue["archived_options"] = (queue.get("archived_options", []) + archived)[-200:]
        queue["options"] = remaining
        queue["history"].append({"timestamp_utc": self.now(), "action": "clear_queue", "archived_count": len(archived), "active_count": len(remaining)})
        queue["last_generate_message"] = f"Cola limpiada. Archivadas: {len(archived)}. Activas: {len(remaining)}."
        return self.save_queue(queue)

    def find_option(self, queue, option_id):
        return next((x for x in queue.get("options", []) if x.get("id") == option_id), None)

    def approve(self, option_id):
        queue = self.load_queue()
        item = self.find_option(queue, option_id)
        if not item:
            return {"ok": False, "error": "option_not_found"}
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
        verification = self.verify_files(item.get("expected_files", []))
        item["verification"] = verification
        item["status"] = "verified" if verification.get("ok") else "applied_unverified"
        item["applied_at"] = self.now()
        item["result"] = result
        registry = self.load_registry()
        registry["tools"][item["id"]] = {"title": item.get("title"), "type": item.get("type"), "verified": verification.get("ok"), "verification": verification, "applied_at": item["applied_at"]}
        registry["history"].append({"timestamp_utc": self.now(), "option_id": option_id, "verification_ok": verification.get("ok")})
        self.save_registry(registry)
        queue["history"].append({"timestamp_utc": self.now(), "action": "applied", "option_id": option_id, "verification_ok": verification.get("ok"), "result": result})
        self.save_queue(queue)
        return {"ok": verification.get("ok"), "option": item, "result": result, "verification": verification}

    def apply_lineage_view(self):
        content = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>MICELIO Linaje</title><style>body{margin:0;background:#050816;color:#f7f9ff;font-family:system-ui;padding:14px}.card{background:#0d1730;border:1px solid #8aa4ff33;border-radius:20px;padding:14px;margin:10px 0}.node{background:#14203d;border-radius:14px;padding:10px;margin:8px 0}.muted{color:#9aa8c7;font-size:13px}a{color:#55e6ff}</style></head><body><h1>MICELIO · Linaje</h1><a href='/control.html'>Volver</a><section class='card'><div id='lineage'>Cargando...</div></section><script>async function load(){const r=await fetch('/api/status');const s=await r.json();const top=s.metrics?.top_role_spores||[];document.getElementById('lineage').innerHTML=top.map(x=>`<div class='node'><b>${x.spore_id}</b><p class='muted'>Padre: ${x.parent_id||'root'} · Rol: ${x.role||'—'} · Gen: ${x.generation||'—'} · Score: ${(x.adjusted_score||x.selection_score||0).toFixed(4)}</p></div>`).join('')||'Sin linajes.'}load();setInterval(load,3000)</script></body></html>"""
        (self.repo_dir / "docs" / "lineage.html").write_text(content, encoding="utf-8")
        return {"files_written": ["docs/lineage.html"]}

    def apply_health_monitor(self):
        content = """import json, os, shutil
from datetime import datetime, timezone

def build_health(repo_dir):
    output=os.path.join(repo_dir,'output'); data=os.path.join(repo_dir,'docs','data'); os.makedirs(output,exist_ok=True); os.makedirs(data,exist_ok=True)
    usage=shutil.disk_usage(repo_dir); metrics={}
    p=os.path.join(output,'colony_metrics.json')
    if os.path.exists(p): metrics=json.load(open(p,encoding='utf-8'))
    health={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'disk_free_mb':round(usage.free/1024/1024,2),'disk_used_mb':round(usage.used/1024/1024,2),'cycle':metrics.get('cycle'),'generation':metrics.get('generation'),'selection_pressure':metrics.get('selection_pressure'),'status':'healthy' if usage.free>200*1024*1024 else 'low_disk'}
    for dest in [os.path.join(output,'health_report.json'), os.path.join(data,'health.json')]: json.dump(health,open(dest,'w',encoding='utf-8'),indent=2,ensure_ascii=False)
    return health
"""
        (self.repo_dir / "runner" / "micelio" / "health_monitor.py").write_text(content, encoding="utf-8")
        return {"files_written": ["runner/micelio/health_monitor.py"]}

    def apply_mission_manifest(self):
        mission = {"timestamp_utc": self.now(), "mission": "mejorar_herramientas_locales", "success_metrics": ["herramientas_verificadas", "chat_mas_contextual", "menos_repeticion_de_sugerencias"]}
        self.write_json(self.memory_dir / "evolution_mission.json", mission); self.write_json(self.docs_data_dir / "mission.json", mission)
        return {"files_written": ["memory/evolution_mission.json", "docs/data/mission.json"]}

    def apply_termux_ai_probe(self):
        content = "#!/data/data/com.termux/files/usr/bin/bash\nset -euo pipefail\necho '[MICELIO] Diagnóstico IA local'\ncommand -v ollama >/dev/null 2>&1 && echo 'ollama: instalado' || echo 'ollama: no instalado'\npython - <<'PY'\nimport socket\nfor name,port in [('ollama',11434),('openai-compatible',5001),('llama-cpp',8081)]:\n s=socket.socket(); s.settimeout(.5)\n try: s.connect(('127.0.0.1',port)); print(f'{name}: puerto {port} abierto')\n except Exception: print(f'{name}: puerto {port} cerrado')\n finally: s.close()\nPY\n"
        path = self.repo_dir / "scripts" / "termux_ai_probe.sh"; path.write_text(content, encoding="utf-8"); path.chmod(0o755)
        return {"files_written": ["scripts/termux_ai_probe.sh"]}

    def apply_organism_dashboard_upgrade(self):
        self.write_json(self.docs_data_dir / "organism_upgrade.json", {"timestamp_utc": self.now(), "status": "applied_marker"})
        return {"files_written": ["docs/data/organism_upgrade.json"]}

    def apply_chat_window(self):
        self.write_json(self.docs_data_dir / "chat_window.json", {"timestamp_utc": self.now(), "endpoint": "/api/chat"})
        return {"files_written": ["docs/data/chat_window.json"]}

    def apply_gitignore_cleanup(self):
        path = self.repo_dir / ".gitignore"; existing = path.read_text(encoding="utf-8") if path.exists() else ""; lines = existing.splitlines()
        for item in ["__pycache__/", "*.pyc", ".pytest_cache/", "output/*.log", "*.tmp"]:
            if item not in lines: lines.append(item)
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return {"files_written": [".gitignore"]}

    def apply_construction_verifier(self):
        content = "from pathlib import Path\nfrom datetime import datetime, timezone\n\ndef verify(repo_dir, files):\n    repo=Path(repo_dir); out=[]\n    for rel in files:\n        p=repo/rel; out.append({'path':rel,'exists':p.exists(),'size_bytes':p.stat().st_size if p.exists() and p.is_file() else None})\n    return {'timestamp_utc':datetime.now(timezone.utc).isoformat(),'ok':all(x['exists'] for x in out),'files':out}\n"
        (self.repo_dir / "runner" / "micelio" / "build_verifier.py").write_text(content, encoding="utf-8")
        self.write_json(self.docs_data_dir / "build_verifier.json", {"timestamp_utc": self.now(), "status": "available"})
        return {"files_written": ["runner/micelio/build_verifier.py", "docs/data/build_verifier.json"]}

    def apply_health_dashboard(self):
        content = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>MICELIO Salud</title><style>body{background:#050816;color:#f7f9ff;font-family:system-ui;padding:14px}.card{background:#0d1730;border-radius:20px;padding:14px;white-space:pre-wrap}a{color:#55e6ff}</style></head><body><h1>Salud MICELIO</h1><a href='/control.html'>Volver</a><div id='box' class='card'>Cargando...</div><script>async function load(){let r=await fetch('/api/status');let s=await r.json();document.getElementById('box').textContent=JSON.stringify({metrics:s.metrics,senses:s.senses?.resources,local_ai:s.local_ai},null,2)}load();setInterval(load,3000)</script></body></html>"""
        (self.repo_dir / "docs" / "health.html").write_text(content, encoding="utf-8")
        return {"files_written": ["docs/health.html"]}

    def apply_evolution_changelog(self):
        content = """<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Evolución tecnológica</title><style>body{background:#050816;color:#f7f9ff;font-family:system-ui;padding:14px}.card{background:#0d1730;border-radius:18px;padding:12px;margin:8px 0}a{color:#55e6ff}</style></head><body><h1>Evolución tecnológica</h1><a href='/control.html'>Volver</a><div id='log'></div><script>async function load(){let r=await fetch('/api/status');let s=await r.json();let h=s.construction?.history||[];document.getElementById('log').innerHTML=h.slice().reverse().map(x=>`<div class='card'><b>${x.action}</b><pre>${JSON.stringify(x,null,2)}</pre></div>`).join('')}load();setInterval(load,3000)</script></body></html>"""
        (self.repo_dir / "docs" / "evolution_log.html").write_text(content, encoding="utf-8")
        return {"files_written": ["docs/evolution_log.html"]}

    def apply_chat_reasoning_upgrade(self):
        self.write_json(self.memory_dir / "chat_personality.json", {"timestamp_utc": self.now(), "mode": "estado_hipotesis_accion"})
        self.write_json(self.docs_data_dir / "chat_capabilities.json", {"timestamp_utc": self.now(), "capabilities": ["estado", "construcciones", "ia_local", "diagnostico"]})
        return {"files_written": ["memory/chat_personality.json", "docs/data/chat_capabilities.json"]}
