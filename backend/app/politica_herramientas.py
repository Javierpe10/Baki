"""
Política de permisos para las herramientas del agente.

Módulo puro: no importa el SDK ni hace E/S. El adaptador del hook
PreToolUse solo traduce la decisión a la respuesta que espera el SDK.

Niveles:
- Nivel 1: sin confirmación (búsqueda web y lecturas dentro de raíces ya aprobadas).
- Nivel 2: denegado en el hook; queda pendiente de aprobación con los
  argumentos exactos. BAKI ejecuta solo después de aprobar.
- Desconocido: denegado. Fail-closed.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PERMITIR = "permitir"
DENEGAR_PEDIR_APROBACION = "denegar_pedir_aprobacion"
DENEGAR = "denegar"

# Herramientas integradas del SDK que no escriben nada.
HERRAMIENTAS_NIVEL_1 = {"WebSearch", "WebFetch"}

# Lecturas de archivos del servidor MCP propio de BAKI.
# Nivel 1 solo dentro de raíces aprobadas; fuera, pide aprobación.
HERRAMIENTAS_LECTURA_ARCHIVOS = {
    "mcp__baki__read_file",
    "mcp__baki__list_dir",
}

# Toda acción que escribe, envía, borra, mueve o publica.
HERRAMIENTAS_NIVEL_2 = {
    "mcp__baki__create_file",
    "mcp__baki__delete_file",
    "mcp__baki__move_file",
    "mcp__baki__send_email",
    "mcp__baki__create_event",
    "mcp__baki__update_event",
    "mcp__baki__delete_event",
}


@dataclass(frozen=True)
class Decision:
    accion: str
    motivo: str


def _dentro_de_raices(ruta: Any, raices: Iterable[str]) -> bool:
    """True solo si la ruta es absoluta y, tras resolver '..', cae dentro de una raíz."""

    if not isinstance(ruta, str) or not ruta.strip():
        return False

    candidata = Path(ruta)

    if not candidata.is_absolute():
        return False

    resuelta = candidata.resolve()

    return any(
        resuelta.is_relative_to(Path(raiz).resolve())
        for raiz in raices
    )


def evaluar(
    nombre: str,
    entrada: Any,
    raices_aprobadas: Iterable[str],
) -> Decision:
    """Decide qué hacer con una llamada a herramienta. No tiene efectos."""

    if not isinstance(entrada, dict):
        return Decision(DENEGAR, "Los argumentos de la herramienta no son válidos.")

    if nombre in HERRAMIENTAS_NIVEL_1:
        return Decision(PERMITIR, "Nivel 1: consulta sin escritura.")

    if nombre in HERRAMIENTAS_LECTURA_ARCHIVOS:
        if _dentro_de_raices(entrada.get("path"), raices_aprobadas):
            return Decision(PERMITIR, "Nivel 1: lectura dentro de una carpeta aprobada.")
        return Decision(
            DENEGAR_PEDIR_APROBACION,
            "La lectura fuera de las carpetas aprobadas requiere tu aprobación.",
        )

    if nombre in HERRAMIENTAS_NIVEL_2:
        return Decision(
            DENEGAR_PEDIR_APROBACION,
            "Esta acción requiere tu aprobación antes de ejecutarse.",
        )

    return Decision(DENEGAR, "Herramienta no incluida en la política.")


def huella(nombre: str, entrada: dict) -> str:
    """Huella SHA-256 de la llamada exacta. La aprobación se liga a esta huella."""

    canonico = json.dumps(
        {"tool": nombre, "input": entrada},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def respuesta_hook(decision: Decision) -> dict:
    """
    Traduce la decisión a la salida del hook PreToolUse.
    Un deny aquí bloquea la herramienta aunque el modo de permisos sea permisivo.
    """

    if decision.accion == PERMITIR:
        return {}

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": decision.motivo,
        }
    }
