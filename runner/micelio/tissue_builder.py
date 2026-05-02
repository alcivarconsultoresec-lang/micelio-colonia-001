import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone


TISSUE_DEFINITIONS = {
    "tejido_exploracion": {
        "roles": ["exploradora", "colonizadora"],
        "purpose": "descubrir recursos autorizados, variaciones y rutas de expansión controlada",
    },
    "tejido_estabilidad": {
        "roles": ["estabilizadora"],
        "purpose": "conservar linajes robustos y reducir deriva improductiva",
    },
    "tejido_cognitivo": {
        "roles": ["analista", "arquitecta"],
        "purpose": "razonar sobre memoria, arquitectura y construcción de nuevos módulos",
    },
}


ORGANS = {
    "organo_sensorial": {
        "tissues": ["tejido_exploracion"],
        "purpose": "leer entorno local y detectar herramientas disponibles",
    },
    "organo_cognitivo": {
        "tissues": ["tejido_cognitivo"],
        "purpose": "proponer planes, diseños y autocodificación supervisada",
    },
    "organo_homeostasis": {
        "tissues": ["tejido_estabilidad"],
        "purpose": "regular límites, memoria, consumo y seguridad",
    },
}


class TissueBuilder:
    """Builds virtual tissues/organs from role-specialized spores.

    This is a planning and internal-organization layer. It does not self-modify
    code or deploy external processes.
    """

    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.memory_dir = os.path.join(repo_dir, "memory")
        self.output_dir = os.path.join(repo_dir, "output")
        self.dashboard_data_dir = os.path.join(repo_dir, "docs", "data")
        self.state_file = os.path.join(self.memory_dir, "colony_state.json")
        self.report_file = os.path.join(self.output_dir, "tissues_report.json")
        self.dashboard_file = os.path.join(self.dashboard_data_dir, "tissues.json")

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

    def assign_tissues(self, spores):
        groups = defaultdict(list)
        for spore in spores:
            role = spore.get("role") or spore.get("genome", {}).get("rol_evolutivo", "analista")
            assigned = False
            for tissue_name, definition in TISSUE_DEFINITIONS.items():
                if role in definition["roles"]:
                    groups[tissue_name].append(spore)
                    assigned = True
                    break
            if not assigned:
                groups["tejido_cognitivo"].append(spore)
        return groups

    def summarize_tissue(self, tissue_name, spores):
        scores = [float(spore.get("adjusted_score", spore.get("selection_score", 0)) or 0) for spore in spores]
        roles = Counter([spore.get("role") or spore.get("genome", {}).get("rol_evolutivo", "sin_rol") for spore in spores])
        return {
            "name": tissue_name,
            "purpose": TISSUE_DEFINITIONS[tissue_name]["purpose"],
            "spores_count": len(spores),
            "roles": dict(roles),
            "best_score": round(max(scores), 4) if scores else 0,
            "average_score": round(sum(scores) / len(scores), 4) if scores else 0,
            "members": [
                {
                    "spore_id": spore.get("spore_id"),
                    "role": spore.get("role"),
                    "status": spore.get("status"),
                    "score": spore.get("adjusted_score", spore.get("selection_score")),
                    "generation": spore.get("generation"),
                }
                for spore in sorted(spores, key=lambda item: item.get("adjusted_score", item.get("selection_score", 0)), reverse=True)[:8]
            ],
        }

    def build_organs(self, tissue_summary):
        tissue_map = {item["name"]: item for item in tissue_summary}
        organs = []
        for organ_name, definition in ORGANS.items():
            selected = [tissue_map[name] for name in definition["tissues"] if name in tissue_map]
            total_spores = sum(item["spores_count"] for item in selected)
            avg_scores = [item["average_score"] for item in selected if item["average_score"]]
            organs.append(
                {
                    "name": organ_name,
                    "purpose": definition["purpose"],
                    "tissues": [item["name"] for item in selected],
                    "spores_count": total_spores,
                    "operational_score": round(sum(avg_scores) / len(avg_scores), 4) if avg_scores else 0,
                    "status": "virtual_ready" if total_spores > 0 else "missing_tissue",
                }
            )
        return organs

    def build(self):
        state = self.read_json(self.state_file, {})
        spores = state.get("virtual_spores", [])
        groups = self.assign_tissues(spores)
        tissue_summary = [self.summarize_tissue(name, group) for name, group in groups.items()]
        tissue_summary.sort(key=lambda item: item["average_score"], reverse=True)
        organs = self.build_organs(tissue_summary)

        report = {
            "timestamp_utc": self.now(),
            "phase": "fase_3_tejidos_y_organos_virtuales",
            "tissues": tissue_summary,
            "organs": organs,
            "decision": "organizacion_virtual_creada_sin_despliegue_externo",
            "next_step": "ejecutar pruebas de razonamiento por organo antes de permitir autocodificacion supervisada",
            "safety": "Los órganos son agrupaciones virtuales. No crean procesos ni acceden a recursos fuera del alcance autorizado.",
        }
        state["tissues"] = {item["name"]: item for item in tissue_summary}
        state["organs"] = {item["name"]: item for item in organs}
        self.write_json(self.state_file, state)
        self.write_json(self.report_file, report)
        self.write_json(self.dashboard_file, report)
        return report
