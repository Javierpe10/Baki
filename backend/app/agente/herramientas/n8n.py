"""n8n: crear, modificar, probar y activar automatizaciones y agentes.

Lecturas: nivel 1. Crear/modificar/activar/borrar/llamar webhooks: nivel 2.
"""

import json

from app.agente.registro import I, ErrorHerramienta, esquema, herramienta, s
from app.integraciones import n8n_cliente as n8n

CAMPOS_ESCRIBIBLES = ("name", "nodes", "connections", "settings", "staticData")


async def _api(*a, **k):
    try:
        return await n8n.api(*a, **k)
    except n8n.N8nNoConfigurado as exc:
        raise ErrorHerramienta(str(exc))


def _resumen_wf(w: dict) -> dict:
    return {
        "id": w.get("id"), "nombre": w.get("name"), "activo": w.get("active"),
        "nodos": [n.get("name") for n in w.get("nodes", [])], "actualizado": w.get("updatedAt"),
        "etiquetas": [t.get("name") for t in w.get("tags", []) or []],
    }


def _validar_nodos(nodos, conexiones) -> None:
    if not isinstance(nodos, list) or not nodos:
        raise ErrorHerramienta("'nodos' debe ser una lista no vacía.")
    nombres = set()
    for n in nodos:
        if not isinstance(n, dict) or not n.get("name") or not n.get("type"):
            raise ErrorHerramienta("Cada nodo necesita al menos 'name' y 'type'.")
        if n["name"] in nombres:
            raise ErrorHerramienta(f"Nombre de nodo repetido: {n['name']}")
        nombres.add(n["name"])
        n.setdefault("typeVersion", 1)
        n.setdefault("position", [0, 0])
        n.setdefault("parameters", {})
    if not isinstance(conexiones, dict):
        raise ErrorHerramienta("'conexiones' debe ser un objeto.")
    for origen, tipos in conexiones.items():
        if origen not in nombres:
            raise ErrorHerramienta(f"La conexión sale de un nodo que no existe: {origen}")
        for salidas in (tipos or {}).values():
            for rama in salidas or []:
                for destino in rama or []:
                    if destino.get("node") not in nombres:
                        raise ErrorHerramienta(f"La conexión apunta a un nodo que no existe: {destino.get('node')}")


def _resumen_crear(e: dict) -> str:
    nodos = e.get("nodos") or []
    lineas = [f"• {n.get('name')} ({str(n.get('type', '')).split('.')[-1]})" for n in nodos[:40] if isinstance(n, dict)]
    return f"Crear en n8n el workflow «{e.get('nombre')}» (inactivo) con {len(nodos)} nodos:\n" + "\n".join(lineas)


@herramienta(
    "n8n_listar_workflows",
    "Lista los workflows de n8n (id, nombre, activo, nodos). Filtro opcional por nombre.",
    esquema({"buscar": s("Texto en el nombre, opcional")}, []),
    nivel=1, resumen=lambda e: "Ver workflows de n8n",
)
async def n8n_listar_workflows(args):
    d = await _api("GET", "/workflows", params={"limit": 250})
    datos = [_resumen_wf(w) for w in d.get("data", [])]
    if args.get("buscar"):
        datos = [w for w in datos if args["buscar"].lower() in (w["nombre"] or "").lower()]
    return datos


@herramienta(
    "n8n_ver_workflow",
    "Devuelve el JSON completo de un workflow de n8n (nodos, parámetros y conexiones).",
    esquema({"id": s("Id del workflow")}, ["id"]),
    nivel=1, resumen=lambda e: f"Ver workflow n8n {e.get('id')}",
)
async def n8n_ver_workflow(args):
    w = await _api("GET", f"/workflows/{args['id']}")
    return {k: w.get(k) for k in ("id", "name", "active", "nodes", "connections", "settings")}


@herramienta(
    "n8n_crear_workflow",
    "Crea un workflow en n8n (queda inactivo). nodos: lista de nodos n8n; conexiones: objeto de conexiones n8n. "
    "Sigue la skill baki:n8n-automatizacion.",
    esquema({
        "nombre": s("Nombre del workflow"),
        "nodos": {"type": "array", "items": {"type": "object"}, "description": "Nodos en formato n8n"},
        "conexiones": {"type": "object", "description": "Conexiones en formato n8n"},
    }, ["nombre", "nodos", "conexiones"]),
    nivel=2, resumen=_resumen_crear,
)
async def n8n_crear_workflow(args):
    _validar_nodos(args["nodos"], args["conexiones"])
    w = await _api("POST", "/workflows", cuerpo={
        "name": args["nombre"], "nodes": args["nodos"], "connections": args["conexiones"],
        "settings": {"executionOrder": "v1"},
    })
    return {"creado": True, **_resumen_wf(w), "url": f"{n8n.base_url()}/workflow/{w.get('id')}"}


@herramienta(
    "n8n_actualizar_workflow",
    "Sustituye nodos y/o conexiones (y opcionalmente el nombre) de un workflow existente. "
    "Lee antes el workflow con n8n_ver_workflow y envía la versión completa modificada.",
    esquema({
        "id": s("Id del workflow"), "nombre": s("Nombre nuevo, opcional"),
        "nodos": {"type": "array", "items": {"type": "object"}},
        "conexiones": {"type": "object"},
        "cambios": s("Descripción breve de lo que cambia, para mostrarla al usuario"),
    }, ["id", "nodos", "conexiones", "cambios"]),
    nivel=2,
    resumen=lambda e: f"Modificar workflow n8n {e.get('id')}: {e.get('cambios')}",
)
async def n8n_actualizar_workflow(args):
    _validar_nodos(args["nodos"], args["conexiones"])
    actual = await _api("GET", f"/workflows/{args['id']}")
    cuerpo = {k: actual.get(k) for k in CAMPOS_ESCRIBIBLES if actual.get(k) is not None}
    cuerpo.update({"nodes": args["nodos"], "connections": args["conexiones"]})
    if args.get("nombre"):
        cuerpo["name"] = args["nombre"]
    cuerpo.setdefault("settings", {"executionOrder": "v1"})
    w = await _api("PUT", f"/workflows/{args['id']}", cuerpo=cuerpo)
    return {"actualizado": True, **_resumen_wf(w)}


@herramienta(
    "n8n_activar",
    "Activa (o desactiva) un workflow de n8n para que se ejecute solo con su disparador.",
    esquema({"id": s("Id del workflow"), "activar": {"type": "boolean", "description": "true activa, false desactiva"},
             "nombre": s("Nombre del workflow, para mostrarlo")}, ["id", "activar"]),
    nivel=2,
    resumen=lambda e: f"{'Activar' if e.get('activar', True) else 'Desactivar'} en n8n: {e.get('nombre') or e.get('id')}",
)
async def n8n_activar(args):
    accion = "activate" if args.get("activar", True) else "deactivate"
    w = await _api("POST", f"/workflows/{args['id']}/{accion}")
    return _resumen_wf(w)


@herramienta(
    "n8n_borrar_workflow",
    "Borra un workflow de n8n (irreversible).",
    esquema({"id": s("Id"), "nombre": s("Nombre, para mostrarlo")}, ["id", "nombre"]),
    nivel=2, resumen=lambda e: f"BORRAR definitivamente en n8n: {e.get('nombre')} ({e.get('id')})",
)
async def n8n_borrar_workflow(args):
    await _api("DELETE", f"/workflows/{args['id']}")
    return "Workflow borrado."


@herramienta(
    "n8n_ejecuciones",
    "Lista las últimas ejecuciones (de un workflow o de todos) con su estado.",
    esquema({"workflow_id": s("Id del workflow, opcional"), "maximo": I}, []),
    nivel=1, resumen=lambda e: "Ver ejecuciones de n8n",
)
async def n8n_ejecuciones(args):
    params = {"limit": min(int(args.get("maximo") or 10), 50)}
    if args.get("workflow_id"):
        params["workflowId"] = args["workflow_id"]
    d = await _api("GET", "/executions", params=params)
    return [{k: e.get(k) for k in ("id", "workflowId", "status", "mode", "startedAt", "stoppedAt")} for e in d.get("data", [])]


@herramienta(
    "n8n_ver_ejecucion",
    "Detalle de una ejecución: estado y salida/error de cada nodo. Úsalo para depurar.",
    esquema({"id": s("Id de la ejecución")}, ["id"]),
    nivel=1, resumen=lambda e: f"Ver ejecución n8n {e.get('id')}",
)
async def n8n_ver_ejecucion(args):
    e = await _api("GET", f"/executions/{args['id']}", params={"includeData": "true"})
    nodos = {}
    run = ((e.get("data") or {}).get("resultData") or {})
    for nombre, ejecuciones in (run.get("runData") or {}).items():
        ultima = ejecuciones[-1] if ejecuciones else {}
        salida = (ultima.get("data") or {}).get("main") or []
        muestra = salida[0][:2] if salida and salida[0] else []
        nodos[nombre] = {"error": (ultima.get("error") or {}).get("message"),
                         "items": sum(len(x or []) for x in salida),
                         "muestra": json.loads(json.dumps(muestra, default=str))[:2]}
    return {"id": e.get("id"), "estado": e.get("status"), "error": (run.get("error") or {}).get("message"), "nodos": nodos}


@herramienta(
    "n8n_llamar_webhook",
    "Llama al webhook de un workflow de n8n para probarlo o dispararlo. modo: 'test' (workflow en escucha) o 'produccion' (activo).",
    esquema({
        "ruta": s("Ruta del webhook (el 'path' del nodo Webhook)"), "metodo": s("POST (por defecto) o GET"),
        "datos": {"type": "object", "description": "Cuerpo JSON de prueba"}, "modo": s("test | produccion"),
    }, ["ruta"]),
    nivel=2,
    resumen=lambda e: f"Llamar al webhook n8n '{e.get('ruta')}' ({e.get('modo', 'test')}) con: "
                      + json.dumps(e.get("datos") or {}, ensure_ascii=False)[:800],
)
async def n8n_llamar_webhook(args):
    try:
        return await n8n.webhook(args["ruta"], args.get("metodo") or "POST", args.get("datos") or {},
                                 prueba=(args.get("modo") or "test") != "produccion")
    except n8n.N8nNoConfigurado as exc:
        raise ErrorHerramienta(str(exc))
