import hashlib
import json
import os
from datetime import datetime, timezone

import requests

RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(RUNNER_DIR)

DATA_FILE = os.path.join(REPO_DIR, "data", "genoma.json")
OUTPUT_FILE = os.path.join(REPO_DIR, "output", "resultados.json")
DEFAULT_MODEL = os.getenv("MICELIO_MODEL", "deepseek-r1:1.5b")
GENERATE_URL = os.getenv("MICELIO_GENERATE_URL")


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

    return (
        f"Objetivo: {objetivo}. "
        f"Especialidad: {especialidad}. "
        f"Capacidades activas: {capacidades}. "
        "Genera una respuesta breve, útil y trazable para la colonia MICELIO."
    )


def generar_respuesta_local(prompt, genoma):
    """Fallback determinístico para que GitHub Actions funcione sin servidor local de IA."""
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


def generar_respuesta_remota(prompt, genoma):
    estrategia = genoma.get("estrategia", {})
    payload = {
        "prompt": prompt,
        "model": DEFAULT_MODEL,
        "temperature": estrategia.get("temperatura", 0.7),
        "max_tokens": 500,
    }

    response = requests.post(GENERATE_URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return {
        "texto": data.get("text", ""),
        "fitness": 1.0,
        "modo": "remote_generator",
        "modelo": DEFAULT_MODEL,
    }


def ejecutar_tarea(genoma):
    prompt = construir_prompt(genoma)

    if not GENERATE_URL:
        resultado = generar_respuesta_local(prompt, genoma)
    else:
        try:
            resultado = generar_respuesta_remota(prompt, genoma)
        except Exception as error:
            resultado = generar_respuesta_local(prompt, genoma)
            resultado["remote_error"] = str(error)

    resultado.update(
        {
            "genoma_id": genoma.get("id", "sin_id"),
            "objetivo": genoma.get("objetivo", "general"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    return resultado


def guardar_resultado(resultado):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(resultado, file, indent=2, ensure_ascii=False)
        file.write("\n")


if __name__ == "__main__":
    genoma = cargar_genoma()
    resultado = ejecutar_tarea(genoma)
    guardar_resultado(resultado)
    print(f"Runner completado. Resultado guardado en {OUTPUT_FILE}")
