import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone


COMMANDS_TO_DETECT = [
    "python",
    "git",
    "curl",
    "termux-info",
    "termux-battery-status",
    "termux-wifi-connectioninfo",
    "ollama",
    "llama-cli",
    "llama-server",
    "node",
    "npm",
    "proot-distro",
    "docker",
    "cloudflared",
]

LOCAL_AI_PORTS = [
    {"name": "ollama", "host": "127.0.0.1", "port": 11434},
    {"name": "llama_cpp_server", "host": "127.0.0.1", "port": 8081},
    {"name": "openai_compatible_local", "host": "127.0.0.1", "port": 5001},
]

SAFE_SCAN_PATHS = [
    "$HOME",
    "$HOME/micelio-colonia-001",
    "$HOME/.termux",
    "/storage/emulated/0/Download",
]


class MobileSenses:
    """Safe local sensory layer for Termux/Android.

    This module only inspects accessible local environment data. It does not crawl
    private app sandboxes, bypass Android permissions, persist in the background,
    or exfiltrate data.
    """

    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.output_dir = os.path.join(repo_dir, "output")
        self.dashboard_data_dir = os.path.join(repo_dir, "docs", "data")
        self.report_file = os.path.join(self.output_dir, "senses_report.json")
        self.dashboard_file = os.path.join(self.dashboard_data_dir, "senses.json")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.dashboard_data_dir, exist_ok=True)

    def now(self):
        return datetime.now(timezone.utc).isoformat()

    def command_exists(self, command):
        return shutil.which(command) is not None

    def run_safe_command(self, command, timeout=6):
        if not self.command_exists(command[0]):
            return {"available": False, "output": None, "error": "command_not_found"}
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return {
                "available": True,
                "returncode": completed.returncode,
                "output": completed.stdout.strip()[:4000],
                "error": completed.stderr.strip()[:1000],
            }
        except Exception as error:
            return {"available": True, "output": None, "error": str(error)}

    def safe_disk_usage(self, path):
        expanded = os.path.expandvars(os.path.expanduser(path))
        if not os.path.exists(expanded):
            return {"path": expanded, "exists": False}
        try:
            usage = shutil.disk_usage(expanded)
            return {
                "path": expanded,
                "exists": True,
                "total_mb": round(usage.total / 1024 / 1024, 2),
                "used_mb": round(usage.used / 1024 / 1024, 2),
                "free_mb": round(usage.free / 1024 / 1024, 2),
            }
        except Exception as error:
            return {"path": expanded, "exists": True, "error": str(error)}

    def memory_info(self):
        info = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as file:
                for line in file.readlines():
                    key, value = line.split(":", 1)
                    if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                        info[key] = value.strip()
        except Exception as error:
            info["error"] = str(error)
        return info

    def port_open(self, host, port, timeout=0.4):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def detect_local_ai(self):
        detected = []
        for item in LOCAL_AI_PORTS:
            detected.append({**item, "open": self.port_open(item["host"], item["port"])})

        ollama = {"binary_available": self.command_exists("ollama"), "models": []}
        if ollama["binary_available"]:
            result = self.run_safe_command(["ollama", "list"], timeout=8)
            ollama["raw"] = result
            if result.get("output"):
                lines = result["output"].splitlines()[1:]
                for line in lines[:20]:
                    parts = line.split()
                    if parts:
                        ollama["models"].append(parts[0])

        return {
            "ports": detected,
            "ollama": ollama,
            "local_ai_available": bool(ollama.get("models")) or any(item["open"] for item in detected),
        }

    def detect_tools(self):
        return {command: self.command_exists(command) for command in COMMANDS_TO_DETECT}

    def detect_termux_api(self):
        battery = self.run_safe_command(["termux-battery-status"], timeout=6)
        wifi = self.run_safe_command(["termux-wifi-connectioninfo"], timeout=6)
        return {
            "battery": self.parse_json_output(battery),
            "wifi": self.parse_json_output(wifi),
            "battery_raw_available": battery.get("available", False),
            "wifi_raw_available": wifi.get("available", False),
        }

    def parse_json_output(self, result):
        if not result.get("output"):
            return {"available": result.get("available", False), "error": result.get("error")}
        try:
            return json.loads(result["output"])
        except json.JSONDecodeError:
            return {"available": result.get("available", False), "raw": result.get("output")}

    def generate_intent(self, local_ai, tools, resources):
        actions = []
        if local_ai.get("local_ai_available"):
            actions.append("usar_ia_local_detectada_para_ciclos_sin_nube")
        else:
            actions.append("mantener_modo_local_fallback_hasta_instalar_ia_local_o_configurar_api")

        if tools.get("termux-battery-status"):
            actions.append("regular_intensidad_por_bateria")
        if tools.get("proot-distro"):
            actions.append("evaluar_contenedor_linux_autorizado_para_futuros_organos")
        if resources.get("storage_download", {}).get("exists"):
            actions.append("usar_download_como_zona_de_intercambio_manual")

        return {
            "purpose": "convertir_esporas_en_tejidos_y_organos_controlados",
            "allowed_scope": "solo_entorno_termux_y_rutas_autorizadas_por_usuario",
            "forbidden_scope": "sin_acceso_a_sandboxes_privados_sin_permiso_sin_persistencia_oculta_sin_exfiltracion",
            "recommended_actions": actions,
        }

    def scan(self):
        tools = self.detect_tools()
        local_ai = self.detect_local_ai()
        resources = {
            "home": self.safe_disk_usage("$HOME"),
            "repo": self.safe_disk_usage(self.repo_dir),
            "storage_download": self.safe_disk_usage("/storage/emulated/0/Download"),
        }
        report = {
            "timestamp_utc": self.now(),
            "phase": "fase_3_sentidos_moviles",
            "runtime": "termux_android" if "com.termux" in os.environ.get("PREFIX", "") else "local",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
                "cpu_count": os.cpu_count(),
            },
            "memory": self.memory_info(),
            "resources": resources,
            "tools": tools,
            "termux_api": self.detect_termux_api(),
            "local_ai": local_ai,
            "intent": self.generate_intent(local_ai, tools, resources),
            "safety": {
                "mode": "authorized_local_sensing_only",
                "note": "No se realiza colonización agresiva ni acceso fuera de permisos de Android/Termux.",
            },
        }
        self.write(report)
        return report

    def write(self, report):
        for path in [self.report_file, self.dashboard_file]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                json.dump(report, file, indent=2, ensure_ascii=False)
                file.write("\n")
