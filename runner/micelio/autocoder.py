import json
import os
from datetime import datetime, timezone


class AutoCoder:
    """Supervised autocoding planner.

    The module creates implementation proposals and patch plans. It does not
    directly rewrite source code, execute arbitrary shell commands, or deploy
    external infrastructure without explicit human approval.
    """

    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.output_dir = os.path.join(repo_dir, "output")
        self.dashboard_data_dir = os.path.join(repo_dir, "docs", "data")
        self.plan_file = os.path.join(self.output_dir, "autocoder_plan.json")
        self.dashboard_file = os.path.join(self.dashboard_data_dir, "autocoder.json")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.dashboard_data_dir, exist_ok=True)

    def now(self):
        return datetime.now(timezone.utc).isoformat()

    def read_json(self, path, default):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")

    def plan(self):
        senses = self.read_json(os.path.join(self.output_dir, "senses_report.json"), {})
        tissues = self.read_json(os.path.join(self.output_dir, "tissues_report.json"), {})
        roles = self.read_json(os.path.join(self.output_dir, "roles_report.json"), {})

        local_ai = senses.get("local_ai", {})
        tools = senses.get("tools", {})
        organs = tissues.get("organs", [])
        roles_summary = roles.get("roles_summary", {})

        tasks = []
        if local_ai.get("local_ai_available"):
            tasks.append({
                "priority": "alta",
                "type": "integration",
                "target": "local_ai_router",
                "description": "Conectar el runner con la IA local detectada antes de usar fallback determinístico.",
                "approval_required": True,
            })
        else:
            tasks.append({
                "priority": "media",
                "type": "capability_gap",
                "target": "local_ai",
                "description": "No se detectó IA local. Mantener fallback o instalar proveedor local autorizado.",
                "approval_required": True,
            })

        if tools.get("proot-distro"):
            tasks.append({
                "priority": "media",
                "type": "environment",
                "target": "linux_container_authorized",
                "description": "Evaluar proot-distro como entorno autorizado para órganos activos de prueba.",
                "approval_required": True,
            })

        if organs:
            tasks.append({
                "priority": "alta",
                "type": "organ_test",
                "target": "organo_cognitivo",
                "description": "Ejecutar benchmark de razonamiento por órgano usando tejidos cognitivos y roles elite.",
                "approval_required": False,
            })

        if roles_summary:
            tasks.append({
                "priority": "alta",
                "type": "selection",
                "target": "role_balancing",
                "description": "Ajustar reproducción para conservar diversidad mínima de castas funcionales.",
                "approval_required": False,
            })

        plan = {
            "timestamp_utc": self.now(),
            "phase": "fase_3_autocodificacion_supervisada",
            "mode": "plan_only",
            "tasks": tasks,
            "guardrails": [
                "no_modificar_codigo_sin_aprobacion_humana",
                "no_ejecutar_comandos_arbitrarios_generados_por_ia",
                "no_desplegar_en_nube_o_docker_sin_permiso_explicito",
                "no_acceder_a_datos_privados_fuera_de_rutas_autorizadas",
            ],
            "next_manual_decision": "aprobar_o_rechazar_tareas_de_autocodificacion",
        }
        self.write_json(self.plan_file, plan)
        self.write_json(self.dashboard_file, plan)
        return plan
