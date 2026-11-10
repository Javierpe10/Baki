"""Gmail y Google Calendar.

Nivel 1: buscar, leer, crear borradores, marcar como leído, ver agenda.
Nivel 2: enviar, responder, enviar a la papelera, crear/mover/borrar eventos.
"""

import asyncio
import base64
import re
from email.message import EmailMessage
from email.utils import getaddresses

from app.agente.registro import B, I, ErrorHerramienta, esquema, herramienta, s
from app.integraciones.google_auth import GoogleNoConfigurado, servicio

MAX_CUERPO = 25_000


async def _g(fn):
    try:
        return await asyncio.to_thread(fn)
    except GoogleNoConfigurado as exc:
        raise ErrorHerramienta(str(exc))
    except Exception as exc:
        # HttpError de Google: devolver solo el estado y el mensaje, nunca cabeceras.
        estado = getattr(getattr(exc, "resp", None), "status", None)
        if estado is not None:
            detalle = getattr(exc, "reason", "") or ""
            raise ErrorHerramienta(f"Google respondió {estado}: {detalle}")
        raise


# ---------------------------------------------------------------- Gmail

def _cabeceras(payload: dict) -> dict:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _texto_mensaje(payload: dict) -> str:
    partes = [payload]
    texto, html = [], []
    while partes:
        p = partes.pop(0)
        partes.extend(p.get("parts", []) or [])
        data = (p.get("body") or {}).get("data")
        if not data:
            continue
        crudo = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        if p.get("mimeType") == "text/plain":
            texto.append(crudo)
        elif p.get("mimeType") == "text/html":
            html.append(crudo)
    if texto:
        return "\n".join(texto)
    limpio = re.sub(r"<(script|style).*?</\1>", "", "\n".join(html), flags=re.S | re.I)
    limpio = re.sub(r"<br\s*/?>|</p>", "\n", limpio, flags=re.I)
    return re.sub(r"<[^>]+>", "", limpio)


@herramienta(
    "gmail_buscar",
    "Busca correos en Gmail con la sintaxis de Gmail (ej: 'is:unread', 'from:cliente@x.com', "
    "'newer_than:2d', 'subject:factura'). Devuelve id, remitente, asunto, fecha y extracto.",
    esquema({"consulta": s("Consulta de Gmail"), "maximo": {**I, "description": "Máximo de resultados (por defecto 10)"}},
            ["consulta"]),
    nivel=1,
    resumen=lambda e: f"Buscar correos: {e.get('consulta')}",
)
async def gmail_buscar(args):
    maximo = min(int(args.get("maximo") or 10), 50)

    def run():
        g = servicio("gmail", "v1").users()
        lista = g.messages().list(userId="me", q=args["consulta"], maxResults=maximo).execute()
        salida = []
        for m in lista.get("messages", []):
            d = g.messages().get(userId="me", id=m["id"], format="metadata",
                                 metadataHeaders=["From", "To", "Subject", "Date"]).execute()
            c = _cabeceras(d["payload"])
            salida.append({
                "id": d["id"], "hilo": d["threadId"], "de": c.get("from"), "para": c.get("to"),
                "asunto": c.get("subject"), "fecha": c.get("date"), "extracto": d.get("snippet"),
                "no_leido": "UNREAD" in d.get("labelIds", []),
            })
        return salida

    return await _g(run)


@herramienta(
    "gmail_leer",
    "Lee un correo completo de Gmail por su id.",
    esquema({"id": s("Id del mensaje")}, ["id"]),
    nivel=1,
    resumen=lambda e: f"Leer el correo {e.get('id')}",
)
async def gmail_leer(args):
    def run():
        d = servicio("gmail", "v1").users().messages().get(userId="me", id=args["id"], format="full").execute()
        c = _cabeceras(d["payload"])
        cuerpo = _texto_mensaje(d["payload"])
        return {
            "id": d["id"], "hilo": d["threadId"], "de": c.get("from"), "para": c.get("to"), "cc": c.get("cc"),
            "asunto": c.get("subject"), "fecha": c.get("date"), "message_id": c.get("message-id"),
            "cuerpo": cuerpo[:MAX_CUERPO],
        }
    return await _g(run)


def _construir(para, asunto, cuerpo, cc=None, responder_a=None) -> dict:
    msg = EmailMessage()
    msg["To"] = para
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    cuerpo_api = {}
    if responder_a:
        g = servicio("gmail", "v1").users()
        orig = g.messages().get(userId="me", id=responder_a, format="metadata",
                                metadataHeaders=["Message-ID", "Subject", "References"]).execute()
        c = _cabeceras(orig["payload"])
        if c.get("message-id"):
            msg["In-Reply-To"] = c["message-id"]
            msg["References"] = (c.get("references", "") + " " + c["message-id"]).strip()
        cuerpo_api["threadId"] = orig["threadId"]
    cuerpo_api["raw"] = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return cuerpo_api


def _validar_destinatarios(*campos):
    for campo in campos:
        if not campo:
            continue
        for _, direccion in getaddresses([campo]):
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", direccion):
                raise ErrorHerramienta(f"Dirección de correo no válida: {direccion!r}")


ESQUEMA_CORREO = esquema({
    "para": s("Destinatarios separados por comas"),
    "asunto": s("Asunto"),
    "cuerpo": s("Texto del correo"),
    "cc": s("Copia, opcional"),
    "responder_a": s("Id del mensaje al que se responde, opcional (mantiene el hilo)"),
}, ["para", "asunto", "cuerpo"])


def _resumen_correo(verbo):
    return lambda e: (f"{verbo} correo a {e.get('para')}" + (f" (cc {e['cc']})" if e.get("cc") else "")
                      + f"\nAsunto: {e.get('asunto')}\n\n{e.get('cuerpo', '')[:1500]}")


@herramienta(
    "gmail_crear_borrador",
    "Crea un borrador en Gmail (no se envía). Úsalo para preparar respuestas que el usuario revisará.",
    ESQUEMA_CORREO, nivel=1, resumen=_resumen_correo("Borrador de"),
)
async def gmail_crear_borrador(args):
    _validar_destinatarios(args["para"], args.get("cc"))

    def run():
        msg = _construir(args["para"], args["asunto"], args["cuerpo"], args.get("cc"), args.get("responder_a"))
        d = servicio("gmail", "v1").users().drafts().create(userId="me", body={"message": msg}).execute()
        return f"Borrador creado (id {d['id']}). No se ha enviado."
    return await _g(run)


@herramienta(
    "gmail_enviar",
    "Envía un correo desde la cuenta de empresa. Siempre requiere aprobación.",
    ESQUEMA_CORREO, nivel=2, resumen=_resumen_correo("Enviar"),
)
async def gmail_enviar(args):
    _validar_destinatarios(args["para"], args.get("cc"))

    def run():
        msg = _construir(args["para"], args["asunto"], args["cuerpo"], args.get("cc"), args.get("responder_a"))
        d = servicio("gmail", "v1").users().messages().send(userId="me", body=msg).execute()
        return f"Correo enviado (id {d['id']})."
    return await _g(run)


@herramienta(
    "gmail_marcar_leido",
    "Marca un correo como leído (o no leído).",
    esquema({"id": s("Id del mensaje"), "leido": {**B, "description": "true = leído"}}, ["id"]),
    nivel=1,
    resumen=lambda e: f"Marcar el correo {e.get('id')} como {'leído' if e.get('leido', True) else 'no leído'}",
)
async def gmail_marcar_leido(args):
    leido = args.get("leido", True)
    cuerpo = {"removeLabelIds": ["UNREAD"]} if leido else {"addLabelIds": ["UNREAD"]}
    await _g(lambda: servicio("gmail", "v1").users().messages().modify(userId="me", id=args["id"], body=cuerpo).execute())
    return "Hecho."


@herramienta(
    "gmail_papelera",
    "Envía un correo a la papelera de Gmail (recuperable 30 días).",
    esquema({"id": s("Id del mensaje"), "descripcion": s("Remitente y asunto, para mostrarlo al usuario")}, ["id", "descripcion"]),
    nivel=2,
    resumen=lambda e: f"Enviar a la papelera el correo: {e.get('descripcion')}",
)
async def gmail_papelera(args):
    await _g(lambda: servicio("gmail", "v1").users().messages().trash(userId="me", id=args["id"]).execute())
    return "Correo enviado a la papelera."


# ---------------------------------------------------------------- Calendar

def _evento(e: dict) -> dict:
    return {
        "id": e.get("id"), "titulo": e.get("summary"),
        "inicio": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
        "fin": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
        "lugar": e.get("location"), "descripcion": (e.get("description") or "")[:500],
        "invitados": [a.get("email") for a in e.get("attendees", [])],
        "meet": e.get("hangoutLink"),
    }


@herramienta(
    "calendario_ver",
    "Lista eventos del calendario principal entre dos fechas (ISO 8601 con zona, ej. 2026-11-09T00:00:00+01:00).",
    esquema({"desde": s("Inicio ISO 8601"), "hasta": s("Fin ISO 8601"), "buscar": s("Texto opcional")}, ["desde", "hasta"]),
    nivel=1,
    resumen=lambda e: f"Ver agenda {e.get('desde')} → {e.get('hasta')}",
)
async def calendario_ver(args):
    def run():
        r = servicio("calendar", "v3").events().list(
            calendarId="primary", timeMin=args["desde"], timeMax=args["hasta"], q=args.get("buscar") or None,
            singleEvents=True, orderBy="startTime", maxResults=100,
        ).execute()
        return [_evento(e) for e in r.get("items", [])]
    return await _g(run)


ESQUEMA_EVENTO = {
    "titulo": s("Título"),
    "inicio": s("Inicio ISO 8601 con zona horaria"),
    "fin": s("Fin ISO 8601 con zona horaria"),
    "descripcion": s("Descripción opcional"),
    "lugar": s("Lugar opcional"),
    "invitados": s("Emails de invitados separados por comas, opcional"),
    "con_meet": {**B, "description": "Crear enlace de Google Meet"},
}


def _cuerpo_evento(a: dict) -> dict:
    cuerpo = {}
    if a.get("titulo"):
        cuerpo["summary"] = a["titulo"]
    if a.get("inicio"):
        cuerpo["start"] = {"dateTime": a["inicio"]}
    if a.get("fin"):
        cuerpo["end"] = {"dateTime": a["fin"]}
    for k, g in (("descripcion", "description"), ("lugar", "location")):
        if a.get(k):
            cuerpo[g] = a[k]
    if a.get("invitados"):
        _validar_destinatarios(a["invitados"])
        cuerpo["attendees"] = [{"email": d.strip()} for d in a["invitados"].split(",") if d.strip()]
    if a.get("con_meet"):
        import uuid
        cuerpo["conferenceData"] = {"createRequest": {"requestId": str(uuid.uuid4()),
                                                      "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
    return cuerpo


def _resumen_evento(verbo):
    return lambda e: (f"{verbo} evento «{e.get('titulo', e.get('id', ''))}» {e.get('inicio', '')} → {e.get('fin', '')}"
                      + (f"\nInvitados (recibirán invitación): {e['invitados']}" if e.get("invitados") else ""))


@herramienta(
    "calendario_crear",
    "Crea un evento en el calendario principal. Si hay invitados, Google les envía la invitación.",
    esquema(ESQUEMA_EVENTO, ["titulo", "inicio", "fin"]),
    nivel=2, resumen=_resumen_evento("Crear"),
)
async def calendario_crear(args):
    def run():
        e = servicio("calendar", "v3").events().insert(
            calendarId="primary", body=_cuerpo_evento(args), conferenceDataVersion=1,
            sendUpdates="all" if args.get("invitados") else "none",
        ).execute()
        return _evento(e)
    return await _g(run)


@herramienta(
    "calendario_modificar",
    "Modifica un evento existente (solo los campos indicados).",
    esquema({"id": s("Id del evento"), **ESQUEMA_EVENTO}, ["id"]),
    nivel=2, resumen=_resumen_evento("Modificar"),
)
async def calendario_modificar(args):
    def run():
        e = servicio("calendar", "v3").events().patch(
            calendarId="primary", eventId=args["id"], body=_cuerpo_evento(args),
            conferenceDataVersion=1, sendUpdates="all",
        ).execute()
        return _evento(e)
    return await _g(run)


@herramienta(
    "calendario_borrar",
    "Borra un evento del calendario (avisa a los invitados).",
    esquema({"id": s("Id del evento"), "descripcion": s("Título y fecha, para mostrarlo al usuario")}, ["id", "descripcion"]),
    nivel=2,
    resumen=lambda e: f"Borrar el evento: {e.get('descripcion')}",
)
async def calendario_borrar(args):
    await _g(lambda: servicio("calendar", "v3").events().delete(
        calendarId="primary", eventId=args["id"], sendUpdates="all").execute())
    return "Evento borrado."
