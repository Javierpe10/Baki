"""GoHighLevel: CRM, conversaciones (SMS, email, Instagram, WhatsApp) y redes sociales.

Lecturas: nivel 1. Cualquier escritura o envío: nivel 2.
"""

import json

from app.agente.registro import ErrorHerramienta, I, esquema, herramienta, s
from app.integraciones import ghl_cliente as ghl


async def _p(*a, **k):
    try:
        return await ghl.peticion(*a, **k)
    except ghl.GhlNoConfigurado as exc:
        raise ErrorHerramienta(str(exc))


def _contacto(c: dict) -> dict:
    return {k: c.get(k) for k in ("id", "firstName", "lastName", "email", "phone", "companyName",
                                  "tags", "source", "dateAdded", "website", "city", "country")}


@herramienta(
    "crm_buscar_contactos",
    "Busca contactos/leads en el CRM (GoHighLevel) por nombre, email, teléfono o empresa.",
    esquema({"consulta": s("Texto a buscar (vacío = últimos contactos)"), "maximo": I}, ["consulta"]),
    nivel=1, resumen=lambda e: f"Buscar en el CRM: {e.get('consulta')}",
)
async def crm_buscar_contactos(args):
    d = await _p("POST", "/contacts/search", cuerpo={
        "locationId": ghl.location_id(), "query": args.get("consulta", ""),
        "pageLimit": min(int(args.get("maximo") or 20), 100),
    })
    return [_contacto(c) for c in d.get("contacts", [])]


@herramienta(
    "crm_ver_contacto",
    "Devuelve la ficha completa de un contacto del CRM.",
    esquema({"id": s("Id del contacto")}, ["id"]),
    nivel=1, resumen=lambda e: f"Ver contacto {e.get('id')}",
)
async def crm_ver_contacto(args):
    return await _p("GET", f"/contacts/{args['id']}")


ESQUEMA_CONTACTO = {
    "nombre": s("Nombre"), "apellido": s("Apellido"), "email": s("Email"), "telefono": s("Teléfono con prefijo"),
    "empresa": s("Empresa"), "web": s("Web"), "etiquetas": s("Etiquetas separadas por comas"),
    "origen": s("Origen del lead, ej. 'BAKI scraping'"), "nota": s("Nota inicial opcional"),
}


def _cuerpo_contacto(c: dict) -> dict:
    mapa = {"nombre": "firstName", "apellido": "lastName", "email": "email", "telefono": "phone",
            "empresa": "companyName", "web": "website", "origen": "source"}
    cuerpo = {v: c[k] for k, v in mapa.items() if c.get(k)}
    if c.get("etiquetas"):
        cuerpo["tags"] = [t.strip() for t in c["etiquetas"].split(",") if t.strip()]
    return cuerpo


@herramienta(
    "crm_crear_contactos",
    "Crea uno o varios contactos/leads en el CRM con una sola aprobación. "
    "'contactos' es una lista JSON de objetos con: nombre, apellido, email, telefono, empresa, web, etiquetas, origen, nota.",
    esquema({"contactos": {"type": "array", "items": {"type": "object", "properties": ESQUEMA_CONTACTO}}}, ["contactos"]),
    nivel=2,
    resumen=lambda e: "Crear en el CRM:\n" + "\n".join(
        f"• {c.get('nombre', '')} {c.get('apellido', '')} · {c.get('empresa', '')} · {c.get('email', '')} {c.get('telefono', '')}"
        for c in (e.get("contactos") or [])[:30]),
)
async def crm_crear_contactos(args):
    contactos = args.get("contactos") or []
    if not contactos or len(contactos) > 100:
        raise ErrorHerramienta("Indica entre 1 y 100 contactos.")
    resultados = []
    for c in contactos:
        try:
            d = await _p("POST", "/contacts/", cuerpo={"locationId": ghl.location_id(), **_cuerpo_contacto(c)})
            cid = (d.get("contact") or {}).get("id")
            if c.get("nota") and cid:
                await _p("POST", f"/contacts/{cid}/notes", cuerpo={"body": c["nota"]})
            resultados.append({"ok": True, "id": cid, "nombre": c.get("nombre")})
        except (ValueError, ErrorHerramienta) as exc:
            resultados.append({"ok": False, "nombre": c.get("nombre"), "error": str(exc)})
    return resultados


@herramienta(
    "crm_actualizar_contacto",
    "Actualiza campos de un contacto del CRM y/o le añade una nota.",
    esquema({"id": s("Id del contacto"), **ESQUEMA_CONTACTO}, ["id"]),
    nivel=2,
    resumen=lambda e: "Actualizar contacto " + e.get("id", "") + ": " + json.dumps(
        {k: v for k, v in e.items() if k != "id"}, ensure_ascii=False)[:800],
)
async def crm_actualizar_contacto(args):
    cuerpo = _cuerpo_contacto(args)
    if cuerpo:
        await _p("PUT", f"/contacts/{args['id']}", cuerpo=cuerpo)
    if args.get("nota"):
        await _p("POST", f"/contacts/{args['id']}/notes", cuerpo={"body": args["nota"]})
    return "Contacto actualizado."


@herramienta(
    "crm_oportunidades",
    "Lista oportunidades del pipeline de ventas, filtrando opcionalmente por texto o estado (open, won, lost).",
    esquema({"buscar": s("Texto opcional"), "estado": s("open | won | lost | all")}, []),
    nivel=1, resumen=lambda e: "Ver oportunidades del CRM",
)
async def crm_oportunidades(args):
    params = {"location_id": ghl.location_id(), "limit": 50}
    if args.get("buscar"):
        params["q"] = args["buscar"]
    if args.get("estado") and args["estado"] != "all":
        params["status"] = args["estado"]
    d = await _p("GET", "/opportunities/search", params=params)
    return [{k: o.get(k) for k in ("id", "name", "status", "monetaryValue", "pipelineStageId", "contactId", "updatedAt")}
            for o in d.get("opportunities", [])]


@herramienta(
    "crm_conversaciones",
    "Lista conversaciones recientes del CRM (SMS, email, Instagram, Facebook, WhatsApp), opcionalmente de un contacto o sin leer.",
    esquema({"contacto_id": s("Id del contacto, opcional"), "sin_leer": {"type": "boolean"}}, []),
    nivel=1, resumen=lambda e: "Ver conversaciones del CRM",
)
async def crm_conversaciones(args):
    params = {"locationId": ghl.location_id(), "limit": 30}
    if args.get("contacto_id"):
        params["contactId"] = args["contacto_id"]
    if args.get("sin_leer"):
        params["status"] = "unread"
    d = await _p("GET", "/conversations/search", params=params)
    return [{k: c.get(k) for k in ("id", "contactId", "fullName", "email", "phone", "lastMessageBody",
                                   "lastMessageType", "lastMessageDate", "unreadCount")}
            for c in d.get("conversations", [])]


@herramienta(
    "crm_leer_mensajes",
    "Lee los mensajes de una conversación del CRM.",
    esquema({"conversacion_id": s("Id de la conversación")}, ["conversacion_id"]),
    nivel=1, resumen=lambda e: f"Leer conversación {e.get('conversacion_id')}",
)
async def crm_leer_mensajes(args):
    d = await _p("GET", f"/conversations/{args['conversacion_id']}/messages", params={"limit": 40})
    msgs = (d.get("messages") or {}).get("messages", []) if isinstance(d.get("messages"), dict) else d.get("messages", [])
    return [{k: m.get(k) for k in ("id", "direction", "messageType", "body", "dateAdded")} for m in msgs]


@herramienta(
    "crm_enviar_mensaje",
    "Envía un mensaje a un contacto desde el CRM. canal: SMS, Email, IG (Instagram DM), FB, WhatsApp, Live_Chat.",
    esquema({
        "contacto_id": s("Id del contacto"), "canal": s("SMS | Email | IG | FB | WhatsApp | Live_Chat"),
        "mensaje": s("Texto del mensaje"), "asunto": s("Asunto (solo Email)"),
    }, ["contacto_id", "canal", "mensaje"]),
    nivel=2,
    resumen=lambda e: f"Enviar {e.get('canal')} al contacto {e.get('contacto_id')}:\n{e.get('mensaje', '')[:1500]}",
)
async def crm_enviar_mensaje(args):
    cuerpo = {"type": args["canal"], "contactId": args["contacto_id"], "message": args["mensaje"]}
    if args["canal"] == "Email":
        cuerpo["subject"] = args.get("asunto") or "(sin asunto)"
        cuerpo["html"] = args["mensaje"].replace("\n", "<br>")
    d = await _p("POST", "/conversations/messages", cuerpo=cuerpo)
    return f"Mensaje enviado ({d.get('messageId') or d.get('conversationId') or 'ok'})."


@herramienta(
    "redes_cuentas",
    "Lista las cuentas de redes sociales conectadas al planificador del CRM (Instagram, Facebook, LinkedIn, Google Business...).",
    esquema({}, []),
    nivel=1, resumen=lambda e: "Ver cuentas de redes sociales",
)
async def redes_cuentas(args):
    return await _p("GET", f"/social-media-posting/{ghl.location_id()}/accounts")


@herramienta(
    "redes_publicar",
    "Publica o programa un post en redes sociales mediante el planificador del CRM. "
    "cuentas: ids de redes_cuentas separados por comas; imagenes: URLs públicas separadas por comas; "
    "programar_para: ISO 8601 opcional (vacío = publicar ya).",
    esquema({
        "cuentas": s("Ids de cuenta separados por comas"), "texto": s("Texto del post"),
        "imagenes": s("URLs de imágenes, opcional"), "programar_para": s("Fecha ISO 8601, opcional"),
    }, ["cuentas", "texto"]),
    nivel=2,
    resumen=lambda e: (f"Publicar en redes ({e.get('cuentas')})"
                       + (f" el {e['programar_para']}" if e.get("programar_para") else " ahora")
                       + f":\n{e.get('texto', '')[:1500]}" + (f"\nImágenes: {e['imagenes']}" if e.get("imagenes") else "")),
)
async def redes_publicar(args):
    cuerpo = {
        "accountIds": [c.strip() for c in args["cuentas"].split(",") if c.strip()],
        "summary": args["texto"],
        "type": "post",
        "media": [{"url": u.strip(), "type": "image/jpeg"} for u in (args.get("imagenes") or "").split(",") if u.strip()],
    }
    if args.get("programar_para"):
        cuerpo["scheduleDate"] = args["programar_para"]
        cuerpo["status"] = "scheduled"
    return await _p("POST", f"/social-media-posting/{ghl.location_id()}/posts", cuerpo=cuerpo)


def _nivel_api(entrada: dict, config: dict) -> int:
    return 1 if str(entrada.get("metodo", "")).upper() == "GET" else 2


@herramienta(
    "crm_api",
    "Llamada directa a la API v2 de GoHighLevel para lo que no cubran las otras herramientas "
    "(calendarios, citas, pipelines, workflows, formularios, webs/funnels, productos, facturas). "
    "ruta empieza por '/', ej. '/calendars/'. locationId se añade si incluyes {location} en la ruta o los parámetros.",
    esquema({
        "metodo": s("GET | POST | PUT | DELETE"), "ruta": s("Ruta de la API, ej. /calendars/"),
        "parametros": {"type": "object", "description": "Query params"},
        "cuerpo": {"type": "object", "description": "Cuerpo JSON"},
        "motivo": s("Qué hace la llamada, en una frase"),
    }, ["metodo", "ruta", "motivo"]),
    nivel=_nivel_api,
    resumen=lambda e: f"API CRM {e.get('metodo')} {e.get('ruta')} — {e.get('motivo')}\n"
                      + json.dumps(e.get("cuerpo") or {}, ensure_ascii=False)[:1200],
)
async def crm_api(args):
    loc = ghl.location_id()
    ruta = args["ruta"].replace("{location}", loc)
    params = {k: (loc if v == "{location}" else v) for k, v in (args.get("parametros") or {}).items()}
    cuerpo = args.get("cuerpo")
    if isinstance(cuerpo, dict):
        cuerpo = {k: (loc if v == "{location}" else v) for k, v in cuerpo.items()}
    return await _p(args["metodo"], ruta, params=params or None, cuerpo=cuerpo)
