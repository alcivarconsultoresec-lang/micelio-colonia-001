import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_DIR / "docs"
MEMORY_DIR = REPO_DIR / "memory"
OUTPUT_DIR = REPO_DIR / "output"
DATA_DIR = DOCS_DIR / "data"
CONFIG_FILE = MEMORY_DIR / "admin_config.json"
CONTROL_LOG = OUTPUT_DIR / "control_server.log"

DEFAULT_CONFIG = {
    "mode": "intensivo_controlado",
    "cycles": 5,
    "sleep_seconds": 10,
    "micelio_max_virtual_spores": 64,
    "micelio_max_children_per_cycle": 3,
    "micelio_max_survivors": 24,
    "micelio_max_active_candidates": 5,
    "micelio_model": "openai/gpt-4o-mini",
    "micelio_local_model": "",
    "micelio_local_max_tokens": 350,
    "micelio_disable_local_ai": False,
    "auto_commit": True,
    "auto_push": False,
    "allow_wakelock": True,
    "purpose": "evolucion_controlada_local",
}

STATE = {
    "running": False,
    "current_job": None,
    "last_job": None,
    "started_at": None,
    "log_tail": [],
}
LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs():
    for path in [MEMORY_DIR, OUTPUT_DIR, DATA_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def read_json(path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"error": str(error), "default": default}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_config():
    config = DEFAULT_CONFIG.copy()
    stored = read_json(CONFIG_FILE, {})
    if isinstance(stored, dict):
        config.update(stored)
    return config


def save_config(data):
    config = load_config()
    allowed = set(DEFAULT_CONFIG.keys())
    for key, value in data.items():
        if key in allowed:
            config[key] = value
    config["updated_at"] = now()
    write_json(CONFIG_FILE, config)
    write_json(DATA_DIR / "admin_config.json", config)
    return config


def append_log(line):
    text = f"[{now()}] {line}"
    CONTROL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CONTROL_LOG.open("a", encoding="utf-8") as file:
        file.write(text + "\n")
    with LOCK:
        STATE["log_tail"].append(text)
        STATE["log_tail"] = STATE["log_tail"][-80:]


def env_from_config(config):
    env = os.environ.copy()
    env.update(
        {
            "MICELIO_MAX_VIRTUAL_SPORES": str(config.get("micelio_max_virtual_spores", 64)),
            "MICELIO_MAX_CHILDREN_PER_CYCLE": str(config.get("micelio_max_children_per_cycle", 3)),
            "MICELIO_MAX_SURVIVORS": str(config.get("micelio_max_survivors", 24)),
            "MICELIO_MAX_ACTIVE_CANDIDATES": str(config.get("micelio_max_active_candidates", 5)),
            "MICELIO_MODEL": str(config.get("micelio_model", "openai/gpt-4o-mini")),
            "MICELIO_LOCAL_MODEL": str(config.get("micelio_local_model", "")),
            "MICELIO_LOCAL_MAX_TOKENS": str(config.get("micelio_local_max_tokens", 350)),
            "MICELIO_DISABLE_LOCAL_AI": "true" if config.get("micelio_disable_local_ai") else "false",
            "MICELIO_AUTO_PUSH": "true" if config.get("auto_push") else "false",
        }
    )
    return env


def run_command(command, env=None):
    append_log("Ejecutando: " + " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=str(REPO_DIR),
        env=env or os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout or []:
        append_log(line.rstrip())
    code = process.wait()
    append_log(f"Comando terminado con código {code}")
    return code


def git_commit_if_needed(message):
    subprocess.run(["git", "config", "user.name", "micelio-termux"], cwd=REPO_DIR, check=False)
    subprocess.run(["git", "config", "user.email", "micelio-termux@local"], cwd=REPO_DIR, check=False)
    subprocess.run(
        ["git", "add", "output", "memory", "docs/data"],
        cwd=REPO_DIR,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR, check=False)
    if diff.returncode == 0:
        append_log("Sin cambios para commit.")
        return
    subprocess.run(["git", "commit", "-m", message], cwd=REPO_DIR, check=False)
    append_log("Commit local creado: " + message)


def run_cycles(cycles, sleep_seconds):
    config = load_config()
    cycles = max(1, min(int(cycles), 50))
    sleep_seconds = max(0, min(int(sleep_seconds), 300))
    env = env_from_config(config)
    with LOCK:
        if STATE["running"]:
            append_log("Se rechazó ejecución: ya hay un trabajo activo.")
            return
        STATE["running"] = True
        STATE["current_job"] = {"type": "cycles", "cycles": cycles, "sleep_seconds": sleep_seconds, "started_at": now()}
    try:
        append_log(f"Inicio de ciclo controlado: {cycles} ciclo(s), pausa {sleep_seconds}s")
        for index in range(1, cycles + 1):
            append_log(f"Ciclo {index}/{cycles}")
            code = run_command(["python", "runner/espora_runner.py"], env=env)
            if code != 0:
                append_log(f"Ciclo detenido por error código {code}")
                break
            if index < cycles and sleep_seconds > 0:
                time.sleep(sleep_seconds)
        if config.get("auto_commit", True):
            git_commit_if_needed(f"Control Center MICELIO: {cycles} ciclo(s)")
        with LOCK:
            STATE["last_job"] = {**(STATE.get("current_job") or {}), "finished_at": now()}
    finally:
        with LOCK:
            STATE["running"] = False
            STATE["current_job"] = None
        append_log("Trabajo finalizado.")


def wake_lock(enable=True):
    command = "termux-wake-lock" if enable else "termux-wake-unlock"
    if not shutil.which(command):
        return {"ok": False, "error": f"{command} no está instalado. Instala termux-api."}
    result = subprocess.run([command], capture_output=True, text=True, check=False)
    return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}


class ControlHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def send_json(self, data, code=200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_body_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_json(
                {
                    "timestamp_utc": now(),
                    "server": STATE,
                    "config": load_config(),
                    "metrics": read_json(OUTPUT_DIR / "colony_metrics.json", {}),
                    "roles": read_json(OUTPUT_DIR / "roles_report.json", {}),
                    "senses": read_json(OUTPUT_DIR / "senses_report.json", {}),
                    "tissues": read_json(OUTPUT_DIR / "tissues_report.json", {}),
                    "autocoder": read_json(OUTPUT_DIR / "autocoder_plan.json", {}),
                    "local_ai": read_json(OUTPUT_DIR / "local_ai_report.json", {}),
                    "result": read_json(OUTPUT_DIR / "resultados.json", {}),
                }
            )
            return
        if parsed.path == "/api/config":
            self.send_json(load_config())
            return
        if parsed.path == "/api/logs":
            self.send_json({"log_tail": STATE.get("log_tail", [])})
            return
        if parsed.path == "/":
            self.path = "/control.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            data = self.read_body_json()
        except Exception as error:
            self.send_json({"ok": False, "error": str(error)}, 400)
            return

        if parsed.path == "/api/config":
            self.send_json({"ok": True, "config": save_config(data)})
            return
        if parsed.path == "/api/run_once":
            thread = threading.Thread(target=run_cycles, args=(1, 0), daemon=True)
            thread.start()
            self.send_json({"ok": True, "message": "Ciclo iniciado"})
            return
        if parsed.path == "/api/run_loop":
            cycles = int(data.get("cycles", load_config().get("cycles", 5)))
            sleep_seconds = int(data.get("sleep_seconds", load_config().get("sleep_seconds", 10)))
            thread = threading.Thread(target=run_cycles, args=(cycles, sleep_seconds), daemon=True)
            thread.start()
            self.send_json({"ok": True, "message": f"Loop iniciado: {cycles} ciclos"})
            return
        if parsed.path == "/api/wakelock":
            self.send_json(wake_lock(bool(data.get("enable", True))))
            return
        self.send_json({"ok": False, "error": "endpoint_not_found"}, 404)


def main():
    ensure_dirs()
    save_config(load_config())
    port = int(os.getenv("MICELIO_CONTROL_PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), ControlHandler)
    append_log(f"MICELIO Control Server iniciado en http://127.0.0.1:{port}/control.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
