import copy
import hashlib
import json
import os
import platform
import random
import statistics
import uuid
from datetime import datetime, timezone


SAFE_LIMITS = {
    "max_virtual_spores": int(os.getenv("MICELIO_MAX_VIRTUAL_SPORES", "64")),
    "max_children_per_cycle": int(os.getenv("MICELIO_MAX_CHILDREN_PER_CYCLE", "3")),
    "max_survivors": int(os.getenv("MICELIO_MAX_SURVIVORS", "24")),
    "max_active_candidates": int(os.getenv("MICELIO_MAX_ACTIVE_CANDIDATES", "5")),
    "max_temperature": 1.2,
    "min_temperature": 0.1,
    "max_exploration": 0.95,
    "min_exploration": 0.05,
    "replication_mode": "virtual_only",
    "selection_mode": "elitist_safe_selection",
    "allowed_colonies": ["github_actions", "local", "docker", "google_cloud"],
}


class EvolutionEngine:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.output_dir = os.path.join(repo_dir, "output")
        self.memory_dir = os.path.join(repo_dir, "memory")
        self.dashboard_data_dir = os.path.join(repo_dir, "docs", "data")
        self.state_file = os.path.join(self.memory_dir, "colony_state.json")
        self.episodes_file = os.path.join(self.memory_dir, "episodes.jsonl")
        self.report_file = os.path.join(self.output_dir, "autoconciencia.json")
        self.selection_report_file = os.path.join(self.output_dir, "selection_report.json")
        self.metrics_file = os.path.join(self.output_dir, "colony_metrics.json")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.dashboard_data_dir, exist_ok=True)

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
                "extinct_total": 0,
                "selection": {
                    "active_candidates": [],
                    "survivors": [],
                    "extinct_last_cycle": [],
                    "best_score": 0,
                    "average_score": 0,
                },
                "safety_limits": SAFE_LIMITS,
                "last_decision": "bootstrap",
            }

        with open(self.state_file, "r", encoding="utf-8") as file:
            state = json.load(file)

        state.setdefault("virtual_spores", [])
        state.setdefault("lineage", [])
        state.setdefault("extinct_total", 0)
        state.setdefault("selection", {})
        state.setdefault("safety_limits", SAFE_LIMITS)
        return state

    def save_state(self, state):
        state["updated_at"] = self.now()
        with open(self.state_file, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, ensure_ascii=False)
            file.write("\n")

    def append_episode(self, episode):
        with open(self.episodes_file, "a", encoding="utf-8") as file:
            file.write(json.dumps(episode, ensure_ascii=False) + "\n")

    def read_recent_episodes(self, limit=50):
        if not os.path.exists(self.episodes_file):
            return []
        with open(self.episodes_file, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file.readlines() if line.strip()]
        episodes = []
        for line in lines[-limit:]:
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return episodes

    def inventory_files(self):
        inventory = {
            "python_files": [],
            "json_files": [],
            "workflow_files": [],
            "dashboard_files": [],
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
                elif rel_path.startswith("docs/"):
                    inventory["dashboard_files"].append(rel_path)

        for key in ["python_files", "json_files", "workflow_files", "dashboard_files"]:
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
            "selection_mode": SAFE_LIMITS["selection_mode"],
        }

        env["container"] = "docker_detected" if os.path.exists("/.dockerenv") else "not_detected"
        env["google_cloud_project_detected"] = bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
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

        random.seed(f"{parent_id}-{cycle_index}-{self.now()}-{child_id}")
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
            "last_seen_at": self.now(),
            "genome_hash": genome_hash,
            "genome": child,
            "deployment": "not_deployed_virtual_only",
            "selection_score": 0,
            "selection_reason": "new_child_pending_selection",
        }

    def score_spore(self, spore, cycle_index):
        genome = spore.get("genome", {})
        strategy = genome.get("estrategia", {})
        base_fitness = float(genome.get("fitness", 0.5) or 0.5)
        generation = int(spore.get("generation", genome.get("generacion", 1)) or 1)
        age_penalty = min(0.15, max(0, cycle_index - generation) * 0.005)
        exploration = float(strategy.get("exploracion", 0.3) or 0.3)
        temperature = float(strategy.get("temperatura", 0.7) or 0.7)
        mutation_rate = float(strategy.get("tasa_mutacion", 0.1) or 0.1)

        strategy_balance = 0.0
        if 0.2 <= exploration <= 0.8:
            strategy_balance += 0.06
        if 0.3 <= temperature <= 1.0:
            strategy_balance += 0.06
        if 0.03 <= mutation_rate <= 0.25:
            strategy_balance += 0.05

        novelty = min(0.08, generation * 0.01)
        status_bonus = 0.04 if spore.get("status") in {"elite", "survivor", "latente"} else 0
        score = base_fitness + strategy_balance + novelty + status_bonus - age_penalty
        return round(max(0.01, min(score, 0.999)), 4)

    def select_population(self, state, cycle_index):
        population = state.get("virtual_spores", [])
        scored = []
        for spore in population:
            score = self.score_spore(spore, cycle_index)
            spore["selection_score"] = score
            spore["last_seen_at"] = self.now()
            scored.append(spore)

        scored.sort(key=lambda item: item.get("selection_score", 0), reverse=True)
        active_count = min(SAFE_LIMITS["max_active_candidates"], len(scored))
        survivor_count = min(SAFE_LIMITS["max_survivors"], len(scored))

        active_candidates = scored[:active_count]
        survivors = scored[:survivor_count]
        extinct = scored[survivor_count:]

        survivor_ids = {spore["spore_id"] for spore in survivors}
        active_ids = {spore["spore_id"] for spore in active_candidates}

        for spore in survivors:
            if spore["spore_id"] in active_ids:
                spore["status"] = "elite"
                spore["selection_reason"] = "top_fitness_candidate_for_activation"
            else:
                spore["status"] = "survivor"
                spore["selection_reason"] = "kept_as_viable_latent_variant"

        extinct_summary = []
        for spore in extinct:
            spore["status"] = "extinct"
            extinct_summary.append(
                {
                    "spore_id": spore.get("spore_id"),
                    "parent_id": spore.get("parent_id"),
                    "selection_score": spore.get("selection_score"),
                    "generation": spore.get("generation"),
                    "reason": "outcompeted_by_higher_fitness_variants",
                }
            )

        state["virtual_spores"] = [spore for spore in scored if spore.get("spore_id") in survivor_ids]
        state["extinct_total"] = int(state.get("extinct_total", 0)) + len(extinct_summary)

        scores = [spore.get("selection_score", 0) for spore in survivors]
        selection = {
            "mode": SAFE_LIMITS["selection_mode"],
            "active_candidates": self.public_spore_summary(active_candidates),
            "survivors": self.public_spore_summary(survivors),
            "extinct_last_cycle": extinct_summary[:25],
            "extinct_last_cycle_count": len(extinct_summary),
            "best_score": max(scores) if scores else 0,
            "average_score": round(statistics.mean(scores), 4) if scores else 0,
            "selection_pressure": round(len(extinct_summary) / max(1, len(scored)), 4),
        }
        state["selection"] = selection
        return selection

    def public_spore_summary(self, spores):
        summary = []
        for spore in spores:
            genome = spore.get("genome", {})
            strategy = genome.get("estrategia", {})
            summary.append(
                {
                    "spore_id": spore.get("spore_id"),
                    "parent_id": spore.get("parent_id"),
                    "generation": spore.get("generation"),
                    "status": spore.get("status"),
                    "selection_score": spore.get("selection_score"),
                    "fitness": genome.get("fitness"),
                    "temperature": strategy.get("temperatura"),
                    "exploration": strategy.get("exploracion"),
                    "mutation_rate": strategy.get("tasa_mutacion"),
                    "deployment": spore.get("deployment"),
                    "reason": spore.get("selection_reason"),
                }
            )
        return summary

    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")

    def mirror_dashboard_data(self, metrics, selection_report, awareness_report, episodes):
        self.write_json(os.path.join(self.dashboard_data_dir, "metrics.json"), metrics)
        self.write_json(os.path.join(self.dashboard_data_dir, "selection.json"), selection_report)
        self.write_json(os.path.join(self.dashboard_data_dir, "awareness.json"), awareness_report)
        self.write_json(os.path.join(self.dashboard_data_dir, "episodes.json"), episodes)

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
        selection = self.select_population(state, cycle_index)
        state["cycles"] = cycle_index
        state["generation"] = max([child["generation"] for child in state.get("virtual_spores", [])], default=genoma.get("generacion", 1))
        state["last_decision"] = "seleccion_natural_controlada"
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
            "active_candidates": len(selection.get("active_candidates", [])),
            "survivors": len(selection.get("survivors", [])),
            "extinct_last_cycle_count": selection.get("extinct_last_cycle_count", 0),
            "best_score": selection.get("best_score", 0),
            "average_score": selection.get("average_score", 0),
            "selection_pressure": selection.get("selection_pressure", 0),
            "decision": state["last_decision"],
        }
        self.append_episode(episode)
        episodes = self.read_recent_episodes(limit=50)

        awareness_report = {
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
                "seleccion": SAFE_LIMITS["selection_mode"],
                "hijas_creadas_en_ciclo": len(children),
                "candidatas_activas": len(selection.get("active_candidates", [])),
                "supervivientes": len(selection.get("survivors", [])),
                "extintas_total": state.get("extinct_total", 0),
            },
            "seguridad": {
                "limites": SAFE_LIMITS,
                "nota": "La replicación es virtual, seleccionada y controlada. No despliega procesos externos ni coloniza infraestructura sin autorización explícita.",
            },
            "siguiente_accion_recomendada": (
                "Activar pruebas comparativas sobre las candidatas elite antes de permitir cualquier despliegue en Docker o nube autorizada."
            ),
        }

        selection_report = {
            "timestamp_utc": self.now(),
            "phase": "fase_2_seleccion_natural_controlada",
            "cycle": cycle_index,
            "decision": state["last_decision"],
            "selection": selection,
            "children_created": self.public_spore_summary(children),
            "safety": {
                "mode": SAFE_LIMITS["replication_mode"],
                "limits": SAFE_LIMITS,
                "external_deployment": "disabled_until_explicit_authorization",
            },
        }

        metrics = {
            "timestamp_utc": self.now(),
            "colony_id": state.get("colony_id"),
            "cycle": cycle_index,
            "runtime": environment.get("runtime"),
            "mode": ai_result.get("modo"),
            "model": ai_result.get("modelo"),
            "fitness": fitness,
            "best_score": selection.get("best_score", 0),
            "average_score": selection.get("average_score", 0),
            "selection_pressure": selection.get("selection_pressure", 0),
            "virtual_spores": len(state.get("virtual_spores", [])),
            "active_candidates": len(selection.get("active_candidates", [])),
            "survivors": len(selection.get("survivors", [])),
            "extinct_total": state.get("extinct_total", 0),
            "children_created": len(children),
            "generation": state.get("generation"),
            "replication_mode": SAFE_LIMITS["replication_mode"],
            "selection_mode": SAFE_LIMITS["selection_mode"],
            "last_decision": state.get("last_decision"),
            "charts": {
                "episodes": episodes,
            },
        }

        self.write_json(self.report_file, awareness_report)
        self.write_json(self.selection_report_file, selection_report)
        self.write_json(self.metrics_file, metrics)
        self.mirror_dashboard_data(metrics, selection_report, awareness_report, episodes)

        return {
            "fitness_calculado": fitness,
            "children_created": len(children),
            "virtual_spores_total": len(state.get("virtual_spores", [])),
            "active_candidates": len(selection.get("active_candidates", [])),
            "survivors": len(selection.get("survivors", [])),
            "extinct_total": state.get("extinct_total", 0),
            "best_score": selection.get("best_score", 0),
            "average_score": selection.get("average_score", 0),
            "selection_pressure": selection.get("selection_pressure", 0),
            "cycle": cycle_index,
            "colony_decision": state["last_decision"],
            "self_awareness_report": os.path.relpath(self.report_file, self.repo_dir),
            "selection_report": os.path.relpath(self.selection_report_file, self.repo_dir),
            "metrics_report": os.path.relpath(self.metrics_file, self.repo_dir),
            "memory_state": os.path.relpath(self.state_file, self.repo_dir),
            "episodes": os.path.relpath(self.episodes_file, self.repo_dir),
            "dashboard_data": os.path.relpath(self.dashboard_data_dir, self.repo_dir),
        }
