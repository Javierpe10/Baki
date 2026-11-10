"""Cliente de la API pública de n8n (v1).

URL base en baki_config.json (n8n_url, p. ej. https://miempresa.app.n8n.cloud o
http://localhost:5678). Clave en baki:n8n:api_key. Solo se habla con esa URL.
"""

from urllib.parse import quote

import httpx

from app.agente import config as cfg
from app.secrets_store import SecretStoreUnavailable, tienda_por_defecto


class N8nNoConfigurado(RuntimeError):
    pass


def configurado() -> bool:
    try:
        return bool(cfg.cargar().get("n8n_url")) and "baki:n8n:api_key" in tienda_por_defecto().listar()
    except SecretStoreUnavailable:
        return False


def base_url() -> str:
    url = (cfg.cargar().get("n8n_url") or "").rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise N8nNoConfigurado("n8n no está conectado. Javier debe ejecutar: python -m app.secrets_cli conectar-n8n")
    return url


def _clave() -> str:
    try:
        return tienda_por_defecto().leer("baki:n8n:api_key")
    except (KeyError, SecretStoreUnavailable) as exc:
        raise N8nNoConfigurado("Falta la API key de n8n. Ejecuta: python -m app.secrets_cli conectar-n8n") from exc


def _respuesta(r: httpx.Response):
    try:
        datos = r.json()
    except ValueError:
        datos = {"texto": r.text[:3000]}
    if r.status_code >= 400:
        mensaje = datos.get("message") if isinstance(datos, dict) else None
        raise ValueError(f"n8n respondió {r.status_code}: {mensaje or datos}")
    return datos


async def api(metodo: str, ruta: str, params: dict | None = None, cuerpo=None):
    if not ruta.startswith("/") or "://" in ruta or ".." in ruta:
        raise ValueError("Ruta de API no válida.")
    async with httpx.AsyncClient(base_url=base_url() + "/api/v1", timeout=60) as cliente:
        r = await cliente.request(metodo.upper(), ruta, params=params, json=cuerpo,
                                  headers={"X-N8N-API-KEY": _clave(), "Accept": "application/json"})
    return _respuesta(r)


async def webhook(ruta: str, metodo: str, datos, prueba: bool):
    ruta = ruta.strip().lstrip("/")
    if not ruta or ".." in ruta or "://" in ruta:
        raise ValueError("Ruta de webhook no válida.")
    prefijo = "webhook-test" if prueba else "webhook"
    url = f"{base_url()}/{prefijo}/{quote(ruta, safe='/-_')}"
    async with httpx.AsyncClient(timeout=120) as cliente:
        if metodo.upper() == "GET":
            r = await cliente.get(url, params=datos if isinstance(datos, dict) else None)
        else:
            r = await cliente.request(metodo.upper(), url, json=datos)
    return {"estado_http": r.status_code, "respuesta": _texto_o_json(r)}


def _texto_o_json(r: httpx.Response):
    try:
        return r.json()
    except ValueError:
        return r.text[:5000]
