import hashlib
import json
import os
from datetime import datetime, timezone

import requests
from micelio.autocoder import AutoCoder
from micelio.evolution_engine import EvolutionEngine
from micelio.local_ai_router import LocalAIRouter
from micelio.mobile_senses import MobileSenses
from micelio.role_specializer import RoleSpecializer
from micelio.tissue_builder import TissueBuilder

RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(RUNNER_DIR)

DATA_FILE = os.path.join(REPO_DIR, "data", "genoma.json")
OUTPUT_FILE = os.path.join(REPO_DIR, "output", "resultados.json")
DASHBOARD_RESULT_FILE = os.path.join(REPO_DIR, "docs", "data", "resultados.json")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_MODELS_ENDPOINT = os.getenv(
    "GITHUB_MODELS_ENDPOINT",
    "https://models.github.ai/inference/chat/completions",
)
DEFAULT_MODEL = os.getenv("MICELIO_MODEL", "openai/gpt-4o-mini")
GENERATE_URL = os.getenv("MICELIO_GENERATE_URL")
MAX_TOKENS = int(os.getenv("MICELIO_MAX_TOKENS", "500"))


def cargar_genoma():
    if not os.path.exists(DATA_FILE):
        print("No se encontró data/genoma.json. Usando genoma por defecto.")
        return {
            "id": "colonia_dummy",
            "objetivo": "generar_texto",
            "estrategia": {"temperatura": 0.7},
        }

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def construir_prompt(genoma):
    objetivo = genoma.get("objetivo", "generar texto")
    especialidad = genoma.get("especialidad", "general")
    capacidades = ", ".join(genoma.get("capacidades", [])) or "generar_respuesta"
    memoria = genoma.get("memoria", {})
    energia = genoma.get("energia", "no_definida")
    fitness = genoma.get("fitness", "no_definido")

    return (
        "Eres una espora autónoma de la colonia MICELIO. "
        "Tu tarea es producir una salida breve, accionable y registrable.\n\n"
        f"Objetivo: {objetivo}\n"
        f"Especialidad: {especialidad}\n"
        f"Capacidades activas: {capacidades}\n"
        f"Energía: {energia}\n"
        f"Fitness actual: {fitness}\n"
        f"Memoria: {json.dumps(memoria, ensure_ascii=False)}\n\n"
        "Devuelve una respuesta en español con: diagnóstico, acción recomendada y siguiente mutación útil."
    )


def generar_respuesta_local(prompt, genoma):
    """Fallback determinístico para que el sistema funcione aunque ningún proveedor IA responda."""
    semilla = json.dumps(genoma, sort_keys=True, ensure_ascii=False)
    hash_ejecucion = hashlib.sha256(f"{prompt}|{semilla}".encode("utf-8")).hexdigest()[:16]
    objetivo = genoma.get("objetivo", "general")
    especialidad = genoma.get("especialidad", "general")

    return {
        "texto": (
            "Ejecución MICELIO completada en modo local. "
            f"Objetivo procesado: {objetivo}. "
            f"Especialidad: {especialidad}. "
            f"Hash de ejecución: {hash_ejecucion}."
        ),
        "fitness": 0.75,
        "modo": "local_fallback",
        "hash_ejecucion": hash_ejecucion,
    }


def generar_respuesta_custom(prompt, genoma):
    estrategia = genoma.get("estrategia", {})
    payload = {
        "prompt": prompt,
        "model": DEFAULT_MODEL,
        "temperature": estrategia.get("temperatura", 0.7),
        "max_tokens": MAX_TOKENS,
    }

    response = requests.post(GENERATE_URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return {
        "texto": data.get("text", ""),
        "fitness": 1.0,
        "modo": "custom_remote_generator",
        "modelo": DEFAULT_MODEL,
    }


def generar_respuesta_github_models(prompt, genoma):
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN no está disponible para GitHub Models.")

    estrategia = genoma.get("estrategia", {})
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres el núcleo cognitivo de MICELIO. "
                    "Responde de forma concreta, útil y compatible con registros JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": estrategia.get("temperatura", 0.7),
        "max_tokens": MAX_TOKENS,
    }

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    response = requests.post(
        GITHUB_MODELS_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    texto = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})

    return {
        "texto": texto,
        "fitness": 0.95,
        "modo": "github_models",
        "modelo": DEFAULT_MODEL,
        "usage": usage,
    }


def ejecutar_tarea(genoma):
    prompt = construir_prompt(genoma)
    errores = []

    try:
        return enriquecer_resultado(LocalAIRouter(REPO_DIR).generate(prompt, genoma), genoma, errores)
    except Exception as error:
        errores.append({"provider": "local_ai_router", "error": str(error)})

    if GENERATE_URL:
        try:
            resultado = generar_respuesta_custom(prompt, genoma)
        except Exception as error:
            errores.append({"provider": "custom_remote_generator", "error": str(error)})
        else:
            return enriquecer_resultado(resultado, genoma, errores)

    try:
        resultado = generar_respuesta_github_models(prompt, genoma)
    except Exception as error:
        errores.append({"provider": "github_models", "error": str(error)})
        resultado = generar_respuesta_local(prompt, genoma)

    return enriquecer_resultado(resultado, genoma, errores)


def enriquecer_resultado(resultado, genoma, errores=None):
    resultado.update(
        {
            "genoma_id": genoma.get("id", "sin_id"),
            "objetivo": genoma.get("objetivo", "general"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    if errores:
        resultado["errores_proveedores"] = errores
    return resultado


def escribir_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def guardar_resultado(resultado):
    escribir_json(OUTPUT_FILE, resultado)
    escribir_json(DASHBOARD_RESULT_FILE, resultado)


if __name__ == "__main__":
    genoma = cargar_genoma()
    resultado = ejecutar_tarea(genoma)
    engine = EvolutionEngine(REPO_DIR)
    resultado["evolucion"] = engine.evolve(genoma, resultado)
    resultado["roles"] = RoleSpecializer(REPO_DIR).apply()
    resultado["sentidos"] = MobileSenses(REPO_DIR).scan()
    resultado["tejidos"] = TissueBuilder(REPO_DIR).build()
    resultado["autocoder"] = AutoCoder(REPO_DIR).plan()
    guardar_resultado(resultado)
    print(f"Runner completado. Resultado guardado en {OUTPUT_FILE}")
    print(f"Modo usado: {resultado.get('modo')}")
    print(f"Ciclo evolutivo: {resultado.get('evolucion', {}).get('cycle')}")
    print("Roles fase 2.2 aplicados")
    print("Sentidos móviles, tejidos y autocodificación supervisada fase 3 aplicados")
