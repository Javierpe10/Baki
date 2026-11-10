"""Cliente de GoHighLevel (API v2, LeadConnector).

Autenticación con Private Integration Token guardado en
baki:ghl:token (Administrador de credenciales de Windows).
"""

import httpx

from app.agente import config as cfg
from app.secrets_store import SecretStoreUnavailable, tienda_por_defecto

BASE = "https://services.leadconnectorhq.com"
VERSION = "2021-07-28"


class GhlNoConfigurado(RuntimeError):
    pass


def configurado() -> bool:
    try:
        return "baki:ghl:token" in tienda_por_defecto().listar() and bool(cfg.cargar().get("ghl_location_id"))
    except SecretStoreUnavailable:
        return False


def _token() -> str:
    try:
        return tienda_por_defecto().leer("baki:ghl:token")
    except (KeyError, SecretStoreUnavailable) as exc:
        raise GhlNoConfigurado(
            "GoHighLevel no está conectado. Javier debe ejecutar: python -m app.secrets_cli conectar-ghl"
        ) from exc


def location_id() -> str:
    loc = cfg.cargar().get("ghl_location_id")
    if not loc:
        raise GhlNoConfigurado("Falta ghl_location_id. Ejecuta: python -m app.secrets_cli conectar-ghl")
    return loc


async def peticion(metodo: str, ruta: str, params: dict | None = None, cuerpo: dict | None = None) -> dict:
    if not ruta.startswith("/") or "://" in ruta or ".." in ruta:
        raise ValueError("Ruta de API no válida.")
    cabeceras = {
        "Authorization": f"Bearer {_token()}",
        "Version": VERSION,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as cliente:
        r = await cliente.request(metodo.upper(), ruta, params=params, json=cuerpo, headers=cabeceras)
    try:
        datos = r.json()
    except ValueError:
        datos = {"texto": r.text[:2000]}
    if r.status_code >= 400:
        # Nunca incluir cabeceras (llevan el token).
        mensaje = datos.get("message") if isinstance(datos, dict) else None
        raise ValueError(f"GoHighLevel respondió {r.status_code}: {mensaje or datos}")
    return datos
