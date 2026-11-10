"""Lectura de páginas web (scraping) con protección SSRF.

WebSearch y WebFetch (integradas de Claude) cubren búsqueda y resúmenes. Esta
herramienta devuelve el texto y los enlaces reales de la página, útil para
extraer datos (emails de contacto, listados de empresas, precios).
"""

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.agente.registro import ErrorHerramienta, I, esquema, herramienta, s

MAX_BYTES = 3_000_000
MAX_TEXTO = 40_000
MAX_REDIRECCIONES = 5
AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BAKI/1.0"
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_TEL = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def ip_publica(host: str) -> bool:
    """True solo si TODAS las IP del host son públicas (bloquea localhost, red local, metadatos)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped and not ip_publica(str(ip.ipv4_mapped)):
            return False
    return True


def validar_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ErrorHerramienta("Solo se admiten URLs http(s) completas.")
    if p.username or p.password:
        raise ErrorHerramienta("No se admiten URLs con credenciales.")
    if not ip_publica(p.hostname):
        raise ErrorHerramienta("Esa dirección apunta a la red local o no existe; está bloqueada.")
    return url


class _Extractor(HTMLParser):
    SALTAR = {"script", "style", "noscript", "svg", "template"}
    BLOQUES = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "header", "footer"}

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.partes: list[str] = []
        self.enlaces: list[dict] = []
        self.titulo = ""
        self._saltar = 0
        self._en_titulo = False
        self._enlace: dict | None = None

    def handle_starttag(self, tag, attrs):
        if tag in self.SALTAR:
            self._saltar += 1
        if tag == "title":
            self._en_titulo = True
        if tag in self.BLOQUES:
            self.partes.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("javascript:", "#")):
                self._enlace = {"url": urljoin(self.base, href), "texto": ""}

    def handle_endtag(self, tag):
        if tag in self.SALTAR and self._saltar:
            self._saltar -= 1
        if tag == "title":
            self._en_titulo = False
        if tag == "a" and self._enlace:
            self._enlace["texto"] = self._enlace["texto"].strip()[:120]
            self.enlaces.append(self._enlace)
            self._enlace = None

    def handle_data(self, data):
        if self._saltar:
            return
        if self._en_titulo:
            self.titulo += data
        self.partes.append(data)
        if self._enlace is not None:
            self._enlace["texto"] += data


async def descargar(url: str) -> tuple[str, str, str]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers={"User-Agent": AGENTE}) as cliente:
        actual = url
        for _ in range(MAX_REDIRECCIONES + 1):
            await asyncio.to_thread(validar_url, actual)
            async with cliente.stream("GET", actual) as r:
                if r.is_redirect:
                    actual = urljoin(actual, r.headers.get("location", ""))
                    continue
                cuerpo = b""
                async for trozo in r.aiter_bytes():
                    cuerpo += trozo
                    if len(cuerpo) > MAX_BYTES:
                        break
                tipo = r.headers.get("content-type", "")
                return actual, tipo, cuerpo.decode(r.encoding or "utf-8", errors="replace")
        raise ErrorHerramienta("Demasiadas redirecciones.")


@herramienta(
    "leer_web",
    "Descarga una página web y devuelve su título, texto limpio, enlaces y los emails/teléfonos que aparezcan. "
    "Úsalo para scraping, extraer datos de contacto o revisar webs de clientes y competidores.",
    esquema({
        "url": s("URL completa http(s)"),
        "max_enlaces": {**I, "description": "Máximo de enlaces a devolver (por defecto 60)"},
    }, ["url"]),
    nivel=1,
    resumen=lambda e: f"Leer la web {e.get('url')}",
)
async def leer_web(args):
    url_final, tipo, cuerpo = await descargar(validar_url(args["url"]))
    if "html" not in tipo and "<html" not in cuerpo[:500].lower():
        return {"url": url_final, "tipo": tipo, "texto": cuerpo[:MAX_TEXTO]}
    ext = _Extractor(url_final)
    ext.feed(cuerpo)
    texto = re.sub(r"[ \t]+", " ", "".join(ext.partes))
    texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
    vistos, enlaces = set(), []
    for e in ext.enlaces:
        if e["url"] not in vistos:
            vistos.add(e["url"])
            enlaces.append(e)
    return {
        "url": url_final,
        "titulo": ext.titulo.strip(),
        "texto": texto[:MAX_TEXTO],
        "emails": sorted(set(RE_EMAIL.findall(cuerpo)))[:50],
        "telefonos": sorted({t.strip() for t in RE_TEL.findall(texto)})[:30],
        "enlaces": enlaces[: int(args.get("max_enlaces") or 60)],
    }
