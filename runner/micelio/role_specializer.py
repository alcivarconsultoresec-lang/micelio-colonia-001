import json
import os
import statistics
from collections import Counter
from datetime import datetime, timezone


ROLE_RULES = {
    "exploradora": "Alta exploración y mutación. Busca variación genética controlada.",
    "estabilizadora": "Baja mutación y alta consistencia. Conserva patrones útiles.",
    "analista": "Equilibrio de parámetros. Sirve para lectura de memoria y patrones.",
    "arquitecta": "Alta temperatura con exploración media. Propone cambios estructurales.",
    "colonizadora": "Exploración alta con temperatura estable. Evalúa recursos autorizados sin desplegar.",
}


class RoleSpecializer:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.memory_dir = os.path.join(repo_dir, "memory")
        self.output_dir = os.path.join(repo_dir, "output")
        self.dashboard_data_dir = os.path.join(repo_dir, "docs", "data")
        self.state_file = os.path.join(self.memory_dir, "colony_state.json")
        self.metrics_file = os.path.join(self.output_dir, "colony_metrics.json")
        self.selection_file = os.path.join(self.output_dir, "selection_report.json")
        self.roles_report_file = os.path.join(self.output_dir, "roles_report.json")
        self.dashboard_roles_file = os.path.join(self.dashboard_data_dir, "roles.json")

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

    def classify_role(self, spore):
        genome = spore.get("genome", {})
        strategy = genome.get("estrategia", {})
        exploration = float(strategy.get("exploracion", 0.3) or 0.3)
        temperature = float(strategy.get("temperatura", 0.7) or 0.7)
        mutation = float(strategy.get("tasa_mutacion", 0.1) or 0.1)

        if exploration >= 0.68 and mutation >= 0.16:
            return "exploradora"
        if mutation <= 0.08 and 0.45 <= temperature <= 0.85:
            return "estabilizadora"
        if temperature >= 0.85 and 0.35 <= exploration <= 0.7:
            return "arquitecta"
        if exploration >= 0.62 and 0.45 <= temperature <= 0.85:
            return "colonizadora"
        return "analista"

    def role_bonus(self, role, spore):
        score = float(spore.get("selection_score", 0.0) or 0.0)
        if role == "estabilizadora" and score >= 0.68:
            return 0.025
        if role == "exploradora" and score >= 0.62:
            return 0.020
        if role == "colonizadora" and score >= 0.64:
            return 0.018
        if role == "arquitecta" and score >= 0.65:
            return 0.015
        if role == "analista" and score >= 0.66:
            return 0.012
        return 0.0

    def apply_roles_to_spores(self, spores):
        enriched = []
        for spore in spores:
            role = self.classify_role(spore)
            genome = spore.setdefault("genome", {})
            genome["rol_evolutivo"] = role
            genome["descripcion_rol"] = ROLE_RULES[role]
            spore["role"] = role
            spore["role_description"] = ROLE_RULES[role]
            spore["role_bonus"] = self.role_bonus(role, spore)
            spore["adjusted_score"] = round(
                min(0.99, float(spore.get("selection_score", 0) or 0) + spore["role_bonus"]),
                4,
            )
            enriched.append(spore)
        return enriched

    def summarize_roles(self, spores):
        counts = Counter([spore.get("role", "sin_rol") for spore in spores])
        scores_by_role = {}
        for role in counts:
            values = [float(spore.get("adjusted_score", 0) or 0) for spore in spores if spore.get("role") == role]
            scores_by_role[role] = {
                "count": len(values),
                "avg_adjusted_score": round(statistics.mean(values), 4) if values else 0,
                "best_adjusted_score": round(max(values), 4) if values else 0,
                "description": ROLE_RULES.get(role, "Rol no definido"),
            }
        return scores_by_role

    def public_role_spores(self, spores, limit=12):
        ordered = sorted(spores, key=lambda item: item.get("adjusted_score", 0), reverse=True)
        data = []
        for spore in ordered[:limit]:
            genome = spore.get("genome", {})
            strategy = genome.get("estrategia", {})
            data.append(
                {
                    "spore_id": spore.get("spore_id"),
                    "parent_id": spore.get("parent_id"),
                    "generation": spore.get("generation"),
                    "status": spore.get("status"),
                    "role": spore.get("role"),
                    "role_description": spore.get("role_description"),
                    "selection_score": spore.get("selection_score"),
                    "adjusted_score": spore.get("adjusted_score"),
                    "temperature": strategy.get("temperatura"),
                    "exploration": strategy.get("exploracion"),
                    "mutation_rate": strategy.get("tasa_mutacion"),
                }
            )
        return data

    def apply(self):
        state = self.read_json(self.state_file, {})
        spores = state.get("virtual_spores", [])
        if not spores:
            report = {
                "timestamp_utc": self.now(),
                "phase": "fase_2_2_roles",
                "roles_summary": {},
                "top_spores_by_role": [],
                "note": "No hay esporas virtuales para especializar todavía.",
            }
            self.write_json(self.roles_report_file, report)
            self.write_json(self.dashboard_roles_file, report)
            return report

        enriched_spores = self.apply_roles_to_spores(spores)
        state["virtual_spores"] = enriched_spores
        state["role_system"] = {
            "version": "2.2",
            "updated_at": self.now(),
            "roles_available": ROLE_RULES,
        }
        roles_summary = self.summarize_roles(enriched_spores)
        state["roles_summary"] = roles_summary
        self.write_json(self.state_file, state)

        metrics = self.read_json(self.metrics_file, {})
        metrics["phase"] = "fase_2_2_especializacion_de_linajes"
        metrics["roles_summary"] = roles_summary
        metrics["top_role_spores"] = self.public_role_spores(enriched_spores, limit=8)
        self.write_json(self.metrics_file, metrics)
        self.write_json(os.path.join(self.dashboard_data_dir, "metrics.json"), metrics)

        selection = self.read_json(self.selection_file, {})
        selection["role_system"] = {
            "phase": "fase_2_2_especializacion_de_linajes",
            "roles_summary": roles_summary,
        }
        self.write_json(self.selection_file, selection)
        self.write_json(os.path.join(self.dashboard_data_dir, "selection.json"), selection)

        report = {
            "timestamp_utc": self.now(),
            "phase": "fase_2_2_especializacion_de_linajes",
            "roles_available": ROLE_RULES,
            "roles_summary": roles_summary,
            "top_spores_by_role": self.public_role_spores(enriched_spores, limit=12),
            "decision": "castas_funcionales_asignadas_sin_despliegue_externo",
            "safety": "Los roles no habilitan despliegue externo. Solo clasifican funciones internas de la colonia.",
        }
        self.write_json(self.roles_report_file, report)
        self.write_json(self.dashboard_roles_file, report)
        return report
