import copy
import hashlib
import json
import os
import platform
import random
import uuid
from datetime import datetime, timezone


SAFE_LIMITS = {
    "max_virtual_spores": int(os.getenv("MICELIO_MAX_VIRTUAL_SPORES", "64")),
    "max_children_per_cycle": int(os.getenv("MICELIO_MAX_CHILDREN_PER_CYCLE", "3")),
    "max_temperature": 1.2,
    "min_temperature": 0.1,
    "max_exploration": 0.95,
    "min_exploration": 0.05,
    "replication_mode": "virtual_only",
    "allowed_colonies": ["github_actions", "local", "docker", "google_cloud"],
}


class EvolutionEngine:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.output_dir = os.path.join(repo_dir, "output")
        self.memory_dir = os.path.join(repo_dir, "memory")
        self.state_file = os.path.join(self.memory_dir, "colony_state.json")
        self.episodes_file = os.path.join(self.memory_dir, "episodes.jsonl")
        self.report_file = os.path.join(self.output_dir, "autoconciencia.json")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)

    def now(self):
        return datetime.now(timezone.utc).isoformat()

    def load_state(self):
        if not os.path.exists(self.state_file):
            return {
                "colony_id": "micelio-colonia-001",
                "created_at": self.now(),
                "updated_at": self.now(),
                "generation": 1,
                "cycles": 0,
                "virtual_spores": [],
                "lineage": [],
                "safety_limits": SAFE_LIMITS,
                "last_decision": "bootstrap",
            }

        with open(self.state_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def save_state(self, state):
        state["updated_at"] = self.now()
        with open(self.state_file, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, ensure_ascii=False)
            file.write("\n")

    def append_episode(self, episode):
        with open(self.episodes_file, "a", encoding="utf-8") as file:
            file.write(json.dumps(episode, ensure_ascii=False) + "\n")

    def inventory_files(self):
        inventory = {
            "python_files": [],
            "json_files": [],
            "workflow_files": [],
            "total_files_sampled": 0,
        }
        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}

        for root, dirs, files in os.walk(self.repo_dir):
            dirs[:] = [directory for directory in dirs if directory not in ignored_dirs]
            for filename in files:
                rel_path = os.path.relpath(os.path.join(root, filename), self.repo_dir)
                inventory["total_files_sampled"] += 1
                if filename.endswith(".py"):
                    inventory["python_files"].append(rel_path)
                elif filename.endswith(".json"):
                    inventory["json_files"].append(rel_path)
                elif rel_path.startswith(".github/workflows/") and filename.endswith((".yml", ".yaml")):
                    inventory["workflow_files"].append(rel_path)

        for key in ["python_files", "json_files", "workflow_files"]:
            inventory[key] = sorted(inventory[key])[:50]
        return inventory

    def detect_environment(self):
        env = {
            "runtime": "github_actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local",
            "python_version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "cwd": os.getcwd(),
            "repo_dir": self.repo_dir,
            "has_github_token": bool(os.getenv("GITHUB_TOKEN")),
            "has_github_models_endpoint": bool(os.getenv("GITHUB_MODELS_ENDPOINT")),
            "micelio_model": os.getenv("MICELIO_MODEL", "openai/gpt-4o-mini"),
            "virtual_spore_limit": SAFE_LIMITS["max_virtual_spores"],
            "replication_mode": SAFE_LIMITS["replication_mode"],
        }

        if os.path.exists("/.dockerenv"):
            env["container"] = "docker_detected"
        else:
            env["container"] = "not_detected"

        if os.getenv("GOOGLE_CLOUD_PROJECT"):
            env["google_cloud_project_detected"] = True
        else:
            env["google_cloud_project_detected"] = False

        return env

    def calculate_fitness(self, genoma, ai_result, environment, state):
        score = 0.5
        if ai_result.get("modo") == "github_models":
            score += 0.25
        elif ai_result.get("modo") == "local_fallback":
            score += 0.05

        if environment.get("has_github_token"):
            score += 0.05
        if genoma.get("memoria"):
            score += 0.05
        if state.get("cycles", 0) > 0:
            score += 0.05
        if ai_result.get("errores_proveedores"):
            score -= 0.15

        return round(max(0.01, min(score, 0.99)), 4)

    def mutate_genome(self, parent_genoma, cycle_index):
        child = copy.deepcopy(parent_genoma)
        strategy = child.setdefault("estrategia", {})
        parent_id = child.get("id", "unknown")
        child_id = f"g_{uuid.uuid4().hex[:8]}"

        random.seed(f"{parent_id}-{cycle_index}-{self.now()}")
        temperature = float(strategy.get("temperatura", 0.7))
        exploration = float(strategy.get("exploracion", 0.3))
        mutation_rate = float(strategy.get("tasa_mutacion", 0.1))

        strategy["temperatura"] = round(
            min(SAFE_LIMITS["max_temperature"], max(SAFE_LIMITS["min_temperature"], temperature + random.uniform(-0.08, 0.08))),
            3,
        )
        strategy["exploracion"] = round(
            min(SAFE_LIMITS["max_exploration"], max(SAFE_LIMITS["min_exploration"], exploration + random.uniform(-0.06, 0.08))),
            3,
        )
        strategy["tasa_mutacion"] = round(min(0.5, max(0.01, mutation_rate + random.uniform(-0.02, 0.03))), 3)

        child["id"] = child_id
        child["linaje"] = parent_id
        child["generacion"] = int(child.get("generacion", 1)) + 1
        child["fitness"] = round(float(child.get("fitness", 0.5)) * random.uniform(0.92, 1.04), 4)
        child["estado"] = "latente"
        child.setdefault("metadatos", {})["ultima_actualizacion"] = self.now()
        child.setdefault("memoria", {})["ultimas_acciones"] = child.get("memoria", {}).get("ultimas_acciones", [])[-5:]

        genome_hash = hashlib.sha256(json.dumps(child, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        return {
            "spore_id": child_id,
            "parent_id": parent_id,
            "generation": child["generacion"],
            "status": "latente",
            "created_at": self.now(),
            "genome_hash": genome_hash,
            "genome": child,
            "deployment": "not_deployed_virtual_only",
        }

    def evolve(self, genoma, ai_result):
        state = self.load_state()
        environment = self.detect_environment()
        inventory = self.inventory_files()
        previous_cycles = int(state.get("cycles", 0))
        cycle_index = previous_cycles + 1
        fitness = self.calculate_fitness(genoma, ai_result, environment, state)

        current_count = len(state.get("virtual_spores", []))
        available_slots = max(0, SAFE_LIMITS["max_virtual_spores"] - current_count)
        children_to_create = min(SAFE_LIMITS["max_children_per_cycle"], available_slots)

        children = []
        if children_to_create > 0:
            for _ in range(children_to_create):
                children.append(self.mutate_genome(genoma, cycle_index))

        state.setdefault("virtual_spores", []).extend(children)
        state["virtual_spores"] = state["virtual_spores"][-SAFE_LIMITS["max_virtual_spores"] :]
        state["cycles"] = cycle_index
        state["generation"] = max([child["generation"] for child in state["virtual_spores"]], default=genoma.get("generacion", 1))
        state["last_decision"] = "replicacion_virtual_controlada" if children else "limite_virtual_alcanzado"
        state["last_fitness"] = fitness
        state["safety_limits"] = SAFE_LIMITS
        self.save_state(state)

        episode = {
            "timestamp_utc": self.now(),
            "cycle": cycle_index,
            "genoma_id": genoma.get("id"),
            "mode": ai_result.get("modo"),
            "fitness": fitness,
            "children_created": len(children),
            "virtual_spores_total": len(state.get("virtual_spores", [])),
            "decision": state["last_decision"],
        }
        self.append_episode(episode)

        report = {
            "timestamp_utc": self.now(),
            "identidad": {
                "colony_id": state.get("colony_id"),
                "genoma_id": genoma.get("id"),
                "linaje": genoma.get("linaje"),
                "generacion_actual": genoma.get("generacion"),
                "generacion_maxima_colonia": state.get("generation"),
            },
            "entorno": environment,
            "inventario_arquitectura": inventory,
            "fitness": fitness,
            "estado_colonia": {
                "ciclos": state.get("cycles"),
                "esporas_virtuales": len(state.get("virtual_spores", [])),
                "replicacion": SAFE_LIMITS["replication_mode"],
                "hijas_creadas_en_ciclo": len(children),
            },
            "seguridad": {
                "limites": SAFE_LIMITS,
                "nota": "La replicación es virtual y controlada. No despliega procesos externos ni coloniza infraestructura sin autorización explícita.",
            },
            "siguiente_accion_recomendada": (
                "Evaluar fitness de esporas virtuales y activar solo las variantes con mayor desempeño dentro de límites autorizados."
            ),
        }

        with open(self.report_file, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)
            file.write("\n")

        return {
            "fitness_calculado": fitness,
            "children_created": len(children),
            "virtual_spores_total": len(state.get("virtual_spores", [])),
            "cycle": cycle_index,
            "colony_decision": state["last_decision"],
            "self_awareness_report": os.path.relpath(self.report_file, self.repo_dir),
            "memory_state": os.path.relpath(self.state_file, self.repo_dir),
            "episodes": os.path.relpath(self.episodes_file, self.repo_dir),
        }
