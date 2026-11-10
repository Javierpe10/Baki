"""Memoria a largo plazo en la bóveda de Obsidian.

Leer es nivel 1. Escribir es nivel 2 (decisión de Javier del 7 de noviembre:
las escrituras en la bóveda se autorizan como cualquier archivo).
"""

import re
from datetime import datetime

from app.agente.config import VAULT_PATH
from app.agente.registro import ErrorHerramienta, esquema, herramienta, s
from app.obsidian_memory_seccion import ObsidianMemory

CARPETA_MEMORIA = VAULT_PATH / "BAKI" / "Memoria"
_memoria = None


def _mem() -> ObsidianMemory:
    global _memoria
    if _memoria is None:
        _memoria = ObsidianMemory(str(VAULT_PATH))
    return _memoria


@herramienta(
    "buscar_memoria",
    "Busca en la memoria de BAKI (bóveda de Obsidian): datos del usuario, su empresa, preferencias, "
    "clientes, decisiones y notas guardadas. Úsalo antes de preguntar algo que quizá ya sepas.",
    esquema({"consulta": s("Palabras clave")}, ["consulta"]),
    nivel=1,
    resumen=lambda e: f"Buscar en memoria: {e.get('consulta')}",
)
async def buscar_memoria(args):
    resultados = _mem().search(args["consulta"], max_results=5, max_chars=6000)
    if not resultados:
        return "Sin resultados en la memoria."
    return [{"documento": r["document"], "contenido": r["content"]} for r in resultados]


def _nombre_seguro(nombre: str) -> str:
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nombre).strip().strip(".")
    if not limpio:
        raise ErrorHerramienta("Nombre de nota no válido.")
    return limpio[:80]


@herramienta(
    "guardar_memoria",
    "Guarda o amplía una nota en la memoria de BAKI (Obsidian) para recordarlo en el futuro. "
    "Añade al final si la nota ya existe.",
    esquema({
        "nota": s("Título de la nota, por ejemplo 'Clientes' o 'Preferencias de Javier'"),
        "contenido": s("Texto en Markdown a guardar"),
    }, ["nota", "contenido"]),
    nivel=2,
    resumen=lambda e: f"Guardar en memoria «{e.get('nota')}»:\n{e.get('contenido', '')[:500]}",
)
async def guardar_memoria(args):
    CARPETA_MEMORIA.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_MEMORIA / f"{_nombre_seguro(args['nota'])}.md"
    marca = datetime.now().strftime("%Y-%m-%d %H:%M")
    bloque = f"\n\n## {marca}\n\n{args['contenido'].strip()}\n"
    if not ruta.exists():
        bloque = f"# {_nombre_seguro(args['nota'])}\n" + bloque
    with ruta.open("a", encoding="utf-8") as f:
        f.write(bloque)
    return f"Guardado en la memoria: {ruta.name}"
