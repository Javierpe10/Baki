"""Datos para los paneles de la interfaz: skills, conversaciones, actividad y consumo.

Solo lectura. Nada de aquí entra en el prompt del agente.
"""

import json
import re
import uuid
from datetime import datetime

from app.agente import config as cfg

SKILLS_PROPIAS = {"proyecto-nuevo", "n8n-automatizacion", "agente-empresa"}
ORIGEN = {
    "tdd": "Matt Pocock", "grill-me": "Matt Pocock", "grilling": "Matt Pocock", "codebase-design": "Matt Pocock",
    "find-skills": "Vercel",
}
WORKSPACE = cfg.DATA_DIR / "workspace"
CONSUMO = cfg.DATA_DIR / "consumo.jsonl"


def _frontmatter(texto: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", texto, re.S)
    datos = {}
    if m:
        for linea in m.group(1).splitlines():
            if ":" in linea:
                k, v = linea.split(":", 1)
                datos[k.strip()] = v.strip()
    return datos


def listar_skills() -> list[dict]:
    salida = []
    for archivo in sorted((cfg.PLUGIN_DIR / "skills").glob("*/SKILL.md")):
        fm = _frontmatter(archivo.read_text(encoding="utf-8"))
        nombre = fm.get("name") or archivo.parent.name
        salida.append({
            "nombre": nombre,
            "descripcion": fm.get("description", ""),
            "automatica": fm.get("disable-model-invocation", "").lower() != "true",
            "origen": "BAKI" if nombre in SKILLS_PROPIAS else ORIGEN.get(nombre, "Addy Osmani"),
        })
    return salida


def valido(session_id: str) -> bool:
    try:
        uuid.UUID(str(session_id))
        return True
    except ValueError:
        return False


def listar_conversaciones(limite: int = 60) -> list[dict]:
    from claude_agent_sdk import list_sessions

    if not WORKSPACE.is_dir():
        return []
    salida = []
    for s in list_sessions(directory=str(WORKSPACE), limit=limite):
        titulo = (s.custom_title or s.summary or s.first_prompt or "Conversación").strip()
        salida.append({
            "id": s.session_id,
            "titulo": titulo[:90],
            "actualizada": s.last_modified,
            "creada": s.created_at,
        })
    return salida


def _texto_de(contenido) -> str:
    if isinstance(contenido, str):
        return contenido
    partes = []
    for b in contenido or []:
        if isinstance(b, dict) and b.get("type") == "text":
            partes.append(b.get("text", ""))
    return "\n".join(p for p in partes if p)


def mensajes_conversacion(session_id: str) -> dict:
    """Mensajes visibles (texto) y tareas (herramientas usadas) de una conversación."""
    from claude_agent_sdk import get_session_messages

    from app.agente.aprobaciones import resumir
    from app.agente.politica import evaluar
    from app.agente.registro import PREFIJO_MCP

    if not valido(session_id):
        raise ValueError("Id de conversación no válido.")
    config = cfg.cargar()
    mensajes, tareas, por_id = [], [], {}
    for m in get_session_messages(session_id, directory=str(WORKSPACE)):
        contenido = (m.message or {}).get("content")
        if m.type == "user":
            if isinstance(contenido, list):
                for b in contenido:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in por_id:
                        por_id[b["tool_use_id"]]["estado"] = "error" if b.get("is_error") else "hecha"
            texto = _texto_de(contenido).strip()
            # Los prompts de rutinas y los resultados de herramientas no son mensajes del usuario.
            if texto and not texto.startswith("<"):
                mensajes.append({"rol": "usuario", "texto": texto})
        elif m.type == "assistant":
            texto = _texto_de(contenido).strip()
            if texto:
                if mensajes and mensajes[-1]["rol"] == "baki":
                    mensajes[-1]["texto"] += "\n\n" + texto
                else:
                    mensajes.append({"rol": "baki", "texto": texto})
            for b in contenido if isinstance(contenido, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    nombre = b.get("name", "")
                    entrada = b.get("input") or {}
                    tarea = {
                        "id": b.get("id"),
                        "nombre": nombre.removeprefix(PREFIJO_MCP),
                        "resumen": resumir(nombre, entrada)[:300],
                        "nivel": evaluar(nombre, entrada, config).nivel,
                        "estado": "hecha",
                    }
                    por_id[b.get("id")] = tarea
                    tareas.append(tarea)
    return {"id": session_id, "mensajes": mensajes, "tareas": tareas}


def consumo_hoy() -> dict:
    hoy = datetime.now().date()
    turnos, tokens, salida = 0, 0, 0
    try:
        lineas = CONSUMO.read_text(encoding="utf-8").splitlines()
    except OSError:
        lineas = []
    for linea in lineas:
        try:
            d = json.loads(linea)
            if datetime.fromisoformat(d["timestamp"]).astimezone().date() != hoy:
                continue
            uso = d.get("uso") or {}
            turnos += 1
            tokens += sum(int(uso.get(k) or 0) for k in (
                "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            salida += int(uso.get("output_tokens") or 0)
        except (ValueError, KeyError, TypeError):
            continue
    return {"turnos": turnos, "tokens_procesados": tokens, "tokens_generados": salida}


def renombrar_conversacion(session_id: str, titulo: str) -> str:
    """Pone un título propio a una conversación (el SDK guarda el último)."""
    from claude_agent_sdk import rename_session

    if not valido(session_id):
        raise ValueError("Id de conversación no válido.")
    limpio = " ".join(str(titulo or "").split())[:90]
    if not limpio:
        raise ValueError("El nombre no puede estar vacío.")
    if session_id not in {c["id"] for c in listar_conversaciones(500)}:
        raise FileNotFoundError("Conversación no encontrada.")
    rename_session(session_id, limpio, directory=str(WORKSPACE))
    return limpio
