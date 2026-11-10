"""Síntesis de voz para BAKI.

Orden en modo "auto":
1. ElevenLabs, si existe baki:elevenlabs:api_key.
2. Servidor local compatible con OpenAI (/v1/audio/speech), si tts_local_url está
   configurado (por ejemplo Kokoro-FastAPI, Voice Studio u otro servidor local).
3. Voz del navegador (la decide el frontend cuando esto devuelve None).
"""

import httpx

from app.agente import config as cfg
from app.secrets_store import SecretStoreUnavailable, tienda_por_defecto

VOZ_ELEVEN_POR_DEFECTO = "pNInz6obpgDQGcFmaJgB"  # voz multilingüe; cámbiala en baki_config.json


def _clave_eleven() -> str | None:
    try:
        return tienda_por_defecto().leer("baki:elevenlabs:api_key")
    except (KeyError, SecretStoreUnavailable):
        return None


def proveedor() -> str:
    c = cfg.cargar()
    elegido = c.get("tts_proveedor", "auto")
    if elegido in ("navegador", "elevenlabs", "local"):
        if elegido == "elevenlabs" and not _clave_eleven():
            return "navegador"
        if elegido == "local" and not c.get("tts_local_url"):
            return "navegador"
        return elegido
    if _clave_eleven():
        return "elevenlabs"
    if c.get("tts_local_url"):
        return "local"
    return "navegador"


async def sintetizar(texto: str) -> tuple[bytes, str] | None:
    texto = texto.strip()[:2500]
    if not texto:
        return None
    c = cfg.cargar()
    p = proveedor()
    async with httpx.AsyncClient(timeout=60) as cliente:
        if p == "elevenlabs":
            voz = c.get("elevenlabs_voz_id") or VOZ_ELEVEN_POR_DEFECTO
            r = await cliente.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_128",
                headers={"xi-api-key": _clave_eleven() or "", "Content-Type": "application/json"},
                json={"text": texto, "model_id": c.get("elevenlabs_modelo") or "eleven_flash_v2_5",
                      "language_code": "es"},
            )
            if r.status_code == 200:
                return r.content, "audio/mpeg"
            print(f"[tts] ElevenLabs respondió {r.status_code}", flush=True)
            return None
        if p == "local":
            url = c["tts_local_url"].rstrip("/")
            if not url.startswith(("http://127.0.0.1", "http://localhost")):
                print("[tts] tts_local_url debe ser local (127.0.0.1 o localhost)", flush=True)
                return None
            r = await cliente.post(f"{url}/v1/audio/speech", json={
                "model": "tts-1", "input": texto, "voice": c.get("tts_local_voz") or "ef_dora",
                "response_format": "mp3",
            })
            if r.status_code == 200:
                return r.content, r.headers.get("content-type", "audio/mpeg")
            print(f"[tts] servidor local respondió {r.status_code}", flush=True)
            return None
    return None
