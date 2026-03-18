import json
import os
import requests
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'genoma.json')
OUTPUT_FILE = os.path.join(BASE_DIR, 'output', 'resultados.json')

def cargar_genoma():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def ejecutar_tarea(genoma):
    # Simula la ejecución de una espora (similar a ejecutor_espora_v7 pero simplificado)
    prompt = f"Objetivo: {genoma.get('objetivo', 'generar texto')}. Genera una respuesta."
    try:
        response = requests.post('http://localhost:5001/generate', json={
            'prompt': prompt,
            'model': 'deepseek-r1:1.5b',
            'temperature': genoma['estrategia'].get('temperatura', 0.7),
            'max_tokens': 500
        }, timeout=180)
        response.raise_for_status()
        texto = response.json().get('text', '')
        fitness = 1.0  # simplificado
    except Exception as e:
        texto = f"Error: {e}"
        fitness = 0.1
    return {"texto": texto, "fitness": fitness}

def guardar_resultado(resultado):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2)

if __name__ == '__main__':
    if not os.path.exists(DATA_FILE):
        print("No se encontró genoma. Creando uno por defecto...")
        # crear genoma dummy
        genoma = {
            "id": "colonia_dummy",
            "objetivo": "generar_texto",
            "estrategia": {"temperatura": 0.7}
        }
    else:
        genoma = cargar_genoma()
    resultado = ejecutar_tarea(genoma)
    guardar_resultado(resultado)
    print("Runner completado. Resultado guardado en output/")
