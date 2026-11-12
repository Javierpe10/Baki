"""Configuración de BAKI. Vive en backend/data/baki_config.json (sin secretos).

Si el archivo no existe se crea con valores por defecto. Cualquier clave que
falte se completa con el valor por defecto, así que el archivo puede editarse
a mano sin miedo a romperlo.
"""

import json
import os
import threading
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
VAULT_PATH = PROJECT_ROOT / "knowledge" / "BAKI Knowledge"
CONFIG_PATH = DATA_DIR / "baki_config.json"
PLUGIN_DIR = DATA_DIR / "plugin_baki"  # skills de BAKI (plugin local)

HOME = Path.home()


def _defaults() -> dict:
    return {
        "nombre_usuario": "Javier",
        "modelo": os.environ.get("BAKI_MODEL", "claude-sonnet-5-5"),
        "esfuerzo": os.environ.get("BAKI_EFFORT", "medium"),
        "max_turnos": 40,
        # Lecturas, listados y movimientos dentro de estas carpetas no piden
        # confirmación. Fuera de ellas, todo pide confirmación.
        "carpetas_aprobadas": [
            str(HOME / "Desktop"),
            str(HOME / "Documents"),
            str(HOME / "Downloads"),
            str(HOME / "Pictures"),
            str(HOME / "Music"),
            str(HOME / "Videos"),
        ],
        # Proveedor de voz: "auto" usa ElevenLabs si hay clave, luego el
        # servidor local si está configurado, y si no la voz del navegador.
        "tts_proveedor": "auto",
        "tts_local_url": "",
        "tts_local_voz": "",
        "elevenlabs_voz_id": "",
        "elevenlabs_modelo": "eleven_flash_v2_5",
        "palabra_activacion": "baki",
        "ghl_location_id": "",
        "n8n_url": "",
        "carpeta_proyectos": str(HOME / "Desktop" / "Proyectos"),
        "max_turnos_programador": 80,
        # Subagentes que el programador puede lanzar por tarea (panel de clientes, consejo…).
        "max_subagentes_programador": 25,
    }


_lock = threading.Lock()


def cargar() -> dict:
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        datos = _defaults()
        if CONFIG_PATH.exists():
            try:
                guardados = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(guardados, dict):
                    datos.update(guardados)
            except (OSError, json.JSONDecodeError):
                pass
        else:
            CONFIG_PATH.write_text(
                json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return datos


def guardar(cambios: dict) -> dict:
    datos = cargar()
    datos.update(cambios)
    with _lock:
        CONFIG_PATH.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return datos
