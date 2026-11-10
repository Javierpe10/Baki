"""Credenciales OAuth de Google (Gmail y Calendar).

Los valores viven en el Administrador de credenciales de Windows:
  baki:google:client_id, baki:google:client_secret, baki:google:refresh_token
El token de acceso solo existe en memoria.
"""

import json
import threading
from pathlib import Path

from app.secrets_store import SecretStoreUnavailable, tienda_por_defecto

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"

_lock = threading.Lock()
_cache: dict = {}


class GoogleNoConfigurado(RuntimeError):
    pass


def autorizar_desde_json(ruta_json: str) -> None:
    """Flujo de escritorio: abre el navegador, el usuario autoriza y se guarda el refresh token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    datos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    cliente = datos.get("installed") or datos.get("web")
    if not cliente:
        raise ValueError("El JSON no es un cliente OAuth de aplicación de escritorio.")
    flujo = InstalledAppFlow.from_client_config({"installed": cliente}, SCOPES)
    cred = flujo.run_local_server(port=0, prompt="consent", access_type="offline",
                                  authorization_prompt_message="Abriendo el navegador para autorizar a BAKI…")
    if not cred.refresh_token:
        raise RuntimeError("Google no devolvió refresh token. Revoca el acceso y repite.")
    tienda = tienda_por_defecto()
    tienda.guardar("baki:google:client_id", cliente["client_id"])
    tienda.guardar("baki:google:client_secret", cliente["client_secret"])
    tienda.guardar("baki:google:refresh_token", cred.refresh_token)
    _cache.clear()


def configurado() -> bool:
    try:
        tienda = tienda_por_defecto()
        return "baki:google:refresh_token" in tienda.listar()
    except SecretStoreUnavailable:
        return False


def credenciales():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    with _lock:
        cred = _cache.get("cred")
        if cred is None:
            try:
                tienda = tienda_por_defecto()
                cred = Credentials(
                    token=None,
                    refresh_token=tienda.leer("baki:google:refresh_token"),
                    client_id=tienda.leer("baki:google:client_id"),
                    client_secret=tienda.leer("baki:google:client_secret"),
                    token_uri=TOKEN_URI,
                    scopes=SCOPES,
                )
            except (KeyError, SecretStoreUnavailable) as exc:
                raise GoogleNoConfigurado(
                    "Google no está conectado. Javier debe ejecutar: "
                    "python -m app.secrets_cli autorizar-google <ruta del client_secret.json>"
                ) from exc
            _cache["cred"] = cred
        if not cred.valid:
            cred.refresh(Request())
        return cred


def servicio(nombre: str, version: str):
    # Un objeto por llamada: los servicios de googleapiclient no son seguros
    # entre hilos, y con el documento de descubrimiento estático es barato.
    from googleapiclient.discovery import build

    return build(nombre, version, credentials=credenciales(), cache_discovery=False)
