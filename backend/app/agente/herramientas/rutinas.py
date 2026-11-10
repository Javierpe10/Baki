"""Rutinas programadas: BAKI ejecuta una instrucción a una hora fija.

Las rutinas se ejecutan en modo restringido: solo herramientas de nivel 1
(leer, buscar, preparar borradores). Cualquier acción de nivel 2 se deniega
automáticamente y queda anotada en el informe para que la apruebes tú.
"""

import json
import re
import threading
import uuid
from datetime import datetime

from app.agente.config import DATA_DIR
from app.agente.registro import ErrorHerramienta, esquema, herramienta, s

RUTAS_ARCHIVO = DATA_DIR / "rutinas.json"
DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
_lock = threading.Lock()


def cargar() -> list[dict]:
    with _lock:
        if not RUTAS_ARCHIVO.exists():
            return []
        try:
            datos = json.loads(RUTAS_ARCHIVO.read_text(encoding="utf-8"))
            return datos if isinstance(datos, list) else []
        except (OSError, json.JSONDecodeError):
            return []


def guardar(rutinas: list[dict]) -> None:
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        RUTAS_ARCHIVO.write_text(json.dumps(rutinas, ensure_ascii=False, indent=2), encoding="utf-8")


def parsear_dias(texto: str) -> list[str]:
    t = (texto or "todos").lower().replace("é", "e").replace("á", "a")
    if t in ("todos", "diario", "cada dia", "todos los dias"):
        return DIAS[:]
    if t in ("laborables", "entre semana"):
        return DIAS[:5]
    dias = [d.strip()[:3] for d in re.split(r"[,\s]+", t) if d.strip()]
    invalidos = [d for d in dias if d not in DIAS]
    if invalidos or not dias:
        raise ErrorHerramienta("Días no válidos. Usa: todos, laborables o lun,mar,mie,jue,vie,sab,dom.")
    return dias


def toca_ejecutar(rutina: dict, ahora: datetime) -> bool:
    if not rutina.get("activa", True):
        return False
    if DIAS[ahora.weekday()] not in rutina["dias"]:
        return False
    if ahora.strftime("%H:%M") != rutina["hora"]:
        return False
    return rutina.get("ultima_ejecucion") != ahora.strftime("%Y-%m-%d %H:%M")


@herramienta(
    "rutina_crear",
    "Programa una tarea recurrente. Ej.: cada laborable a las 08:30 'resume mis correos sin leer, mi agenda de hoy "
    "y prepara borradores de respuesta'. En las rutinas BAKI solo puede leer y preparar borradores; nunca envía ni borra.",
    esquema({
        "nombre": s("Nombre corto"), "hora": s("HH:MM en 24 h"),
        "dias": s("todos | laborables | lista como lun,mie,vie"), "instruccion": s("Qué debe hacer BAKI"),
    }, ["nombre", "hora", "instruccion"]),
    nivel=2,
    resumen=lambda e: f"Programar rutina «{e.get('nombre')}» ({e.get('dias', 'todos')} a las {e.get('hora')}):\n{e.get('instruccion')}",
)
async def rutina_crear(args):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", args["hora"]):
        raise ErrorHerramienta("La hora debe tener formato HH:MM, por ejemplo 08:30.")
    rutina = {
        "id": uuid.uuid4().hex[:8], "nombre": args["nombre"], "hora": args["hora"],
        "dias": parsear_dias(args.get("dias", "todos")), "instruccion": args["instruccion"], "activa": True,
    }
    rutinas = cargar()
    rutinas.append(rutina)
    guardar(rutinas)
    return rutina


@herramienta(
    "rutinas_listar",
    "Lista las rutinas programadas.",
    esquema({}, []),
    nivel=1, resumen=lambda e: "Ver rutinas",
)
async def rutinas_listar(args):
    return cargar() or "No hay rutinas programadas."


@herramienta(
    "rutina_borrar",
    "Borra una rutina programada por su id.",
    esquema({"id": s("Id de la rutina")}, ["id"]),
    nivel=2, resumen=lambda e: f"Borrar la rutina {e.get('id')}",
)
async def rutina_borrar(args):
    rutinas = cargar()
    nuevas = [r for r in rutinas if r["id"] != args["id"]]
    if len(nuevas) == len(rutinas):
        raise ErrorHerramienta("No existe esa rutina.")
    guardar(nuevas)
    return "Rutina borrada."
