"""Herramientas de archivos y carpetas."""

import asyncio
import fnmatch
import os
import re
import shutil
import zipfile
from pathlib import Path

from app.agente import rutas
from app.agente.registro import ErrorHerramienta, esquema, herramienta, s

MAX_LECTURA = 2_000_000  # bytes leídos del disco
MAX_TEXTO = 60_000  # caracteres devueltos a Claude
MAX_LISTADO = 300
MAX_RESULTADOS = 200
CARPETAS_IGNORADAS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "AppData", "$Recycle.Bin"}


def _nivel_lectura(clave: str):
    def nivel(entrada: dict, config: dict) -> int:
        return 1 if rutas.segura_en_aprobadas(entrada.get(clave), config["carpetas_aprobadas"]) else 2
    return nivel


def _nivel_doble(entrada: dict, config: dict) -> int:
    carpetas = config["carpetas_aprobadas"]
    ok = all(rutas.segura_en_aprobadas(entrada.get(k), carpetas) for k in ("origen", "destino"))
    return 1 if ok else 2


def _texto_docx(ruta: Path) -> str:
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def _texto_pdf(ruta: Path) -> str:
    from pypdf import PdfReader

    lector = PdfReader(str(ruta))
    partes = []
    for i, pagina in enumerate(lector.pages[:60]):
        partes.append(f"--- página {i + 1} ---\n{pagina.extract_text() or ''}")
    return "\n".join(partes)


def _leer(ruta: Path) -> str:
    if not ruta.is_file():
        raise FileNotFoundError("El archivo no existe.")
    sufijo = ruta.suffix.lower()
    if sufijo == ".docx":
        contenido = _texto_docx(ruta)
    elif sufijo == ".pdf":
        contenido = _texto_pdf(ruta)
    else:
        if ruta.stat().st_size > MAX_LECTURA:
            raise ErrorHerramienta("El archivo es demasiado grande para leerlo entero (más de 2 MB).")
        datos = ruta.read_bytes()
        if b"\x00" in datos[:4096]:
            raise ErrorHerramienta("Es un archivo binario; no se puede leer como texto.")
        contenido = datos.decode("utf-8", errors="replace")
    if len(contenido) > MAX_TEXTO:
        contenido = contenido[:MAX_TEXTO] + "\n…[recortado]"
    return contenido


@herramienta(
    "leer_archivo",
    "Lee un archivo de texto, código, .docx o .pdf y devuelve su contenido. Ruta absoluta.",
    esquema({"ruta": s("Ruta absoluta del archivo")}, ["ruta"]),
    nivel=_nivel_lectura("ruta"),
    resumen=lambda e: f"Leer el archivo {e.get('ruta')}",
)
async def leer_archivo(args):
    ruta = rutas.normalizar(args["ruta"])
    return {"ruta": str(ruta), "contenido": await asyncio.to_thread(_leer, ruta)}


@herramienta(
    "listar_carpeta",
    "Lista el contenido de una carpeta (nombres, tipo, tamaño). Ruta absoluta.",
    esquema({"ruta": s("Ruta absoluta de la carpeta")}, ["ruta"]),
    nivel=_nivel_lectura("ruta"),
    resumen=lambda e: f"Ver el contenido de {e.get('ruta')}",
)
async def listar_carpeta(args):
    ruta = rutas.normalizar(args["ruta"])
    if not ruta.is_dir():
        raise FileNotFoundError("La carpeta no existe.")
    entradas = []
    for i, e in enumerate(sorted(ruta.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))):
        if i >= MAX_LISTADO:
            entradas.append({"aviso": "listado recortado"})
            break
        try:
            tam = e.stat().st_size if e.is_file() else None
        except OSError:
            tam = None
        entradas.append({"nombre": e.name, "tipo": "carpeta" if e.is_dir() else "archivo", "bytes": tam})
    return {"ruta": str(ruta), "entradas": entradas}


def _buscar(base: Path, patron: str, texto: str | None) -> list[str]:
    encontrados = []
    texto_l = texto.lower() if texto else None
    for raiz, dirs, archivos in os.walk(base):
        dirs[:] = [d for d in dirs if d not in CARPETAS_IGNORADAS and not d.startswith(".")]
        for nombre in archivos:
            if not fnmatch.fnmatch(nombre.lower(), patron.lower()):
                continue
            completo = Path(raiz) / nombre
            if texto_l:
                try:
                    if completo.stat().st_size > MAX_LECTURA:
                        continue
                    if texto_l not in completo.read_text(encoding="utf-8", errors="ignore").lower():
                        continue
                except OSError:
                    continue
            encontrados.append(str(completo))
            if len(encontrados) >= MAX_RESULTADOS:
                return encontrados
    return encontrados


@herramienta(
    "buscar_archivos",
    "Busca archivos por nombre (patrón tipo *.pdf o *factura*) dentro de una carpeta y sus subcarpetas; "
    "opcionalmente filtra por un texto contenido en el archivo.",
    esquema({
        "carpeta": s("Ruta absoluta donde buscar"),
        "patron": s("Patrón de nombre, por ejemplo *.xlsx o *presupuesto*"),
        "texto": s("Texto opcional que debe contener el archivo"),
    }, ["carpeta", "patron"]),
    nivel=_nivel_lectura("carpeta"),
    resumen=lambda e: f"Buscar {e.get('patron')} en {e.get('carpeta')}",
)
async def buscar_archivos(args):
    base = rutas.normalizar(args["carpeta"])
    if not base.is_dir():
        raise FileNotFoundError("La carpeta no existe.")
    res = await asyncio.to_thread(_buscar, base, args["patron"], args.get("texto"))
    return {"resultados": res, "total": len(res)}


@herramienta(
    "crear_carpeta",
    "Crea una carpeta (y las intermedias que falten).",
    esquema({"ruta": s("Ruta absoluta de la carpeta nueva")}, ["ruta"]),
    nivel=_nivel_lectura("ruta"),
    resumen=lambda e: f"Crear la carpeta {e.get('ruta')}",
)
async def crear_carpeta(args):
    ruta = rutas.para_escritura(args["ruta"])
    ruta.mkdir(parents=True, exist_ok=True)
    return f"Carpeta lista: {ruta}"


def _escribir_verificado(ruta: Path, contenido: str, modo: str) -> int:
    datos = contenido.encode("utf-8")
    with ruta.open(modo) as f:
        f.write(datos)
    if ruta.read_bytes() != datos:
        raise ErrorHerramienta("La verificación falló: el contenido en disco no coincide.")
    return len(datos)


@herramienta(
    "crear_archivo",
    "Crea un archivo de texto nuevo con el contenido indicado. Falla si ya existe.",
    esquema({"ruta": s("Ruta absoluta"), "contenido": s("Contenido completo")}, ["ruta", "contenido"]),
    nivel=2,
    resumen=lambda e: f"Crear el archivo {e.get('ruta')} ({len(e.get('contenido', ''))} caracteres)",
)
async def crear_archivo(args):
    ruta = rutas.para_escritura(args["ruta"])
    if ruta.exists():
        raise FileExistsError("El archivo ya existe. Usa escribir_archivo o editar_archivo.")
    if not ruta.parent.is_dir():
        ruta.parent.mkdir(parents=True, exist_ok=True)
    n = _escribir_verificado(ruta, args["contenido"], "xb")
    return f"Creado y verificado: {ruta} ({n} bytes)"


def _copia_seguridad(ruta: Path) -> Path:
    from app.agente.config import DATA_DIR
    destino_dir = DATA_DIR / "copias"
    destino_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    destino = destino_dir / f"{datetime.now():%Y%m%d-%H%M%S}_{ruta.name}"
    shutil.copy2(ruta, destino)
    return destino


@herramienta(
    "escribir_archivo",
    "Sobrescribe un archivo de texto existente con contenido nuevo (guarda antes una copia de seguridad).",
    esquema({"ruta": s("Ruta absoluta"), "contenido": s("Contenido completo nuevo")}, ["ruta", "contenido"]),
    nivel=2,
    resumen=lambda e: f"Sobrescribir {e.get('ruta')} ({len(e.get('contenido', ''))} caracteres)",
)
async def escribir_archivo(args):
    ruta = rutas.para_escritura(args["ruta"])
    if not ruta.is_file():
        raise FileNotFoundError("El archivo no existe. Usa crear_archivo.")
    copia = _copia_seguridad(ruta)
    n = _escribir_verificado(ruta, args["contenido"], "wb")
    return f"Sobrescrito y verificado: {ruta} ({n} bytes). Copia previa: {copia}"


@herramienta(
    "editar_archivo",
    "Reemplaza un fragmento exacto y único de un archivo de texto por otro. "
    "Úsalo para cambios pequeños en código o documentos.",
    esquema({
        "ruta": s("Ruta absoluta"),
        "buscar": s("Texto exacto a reemplazar; debe aparecer una sola vez"),
        "reemplazar": s("Texto nuevo"),
    }, ["ruta", "buscar", "reemplazar"]),
    nivel=2,
    resumen=lambda e: f"Editar {e.get('ruta')}:\n- {e.get('buscar', '')[:400]}\n+ {e.get('reemplazar', '')[:400]}",
)
async def editar_archivo(args):
    ruta = rutas.para_escritura(args["ruta"])
    if not ruta.is_file():
        raise FileNotFoundError("El archivo no existe.")
    original = ruta.read_bytes().decode("utf-8")
    buscar = args["buscar"]
    if not buscar:
        raise ErrorHerramienta("El texto a buscar no puede estar vacío.")
    veces = original.count(buscar)
    if veces != 1:
        raise ErrorHerramienta(f"El texto a buscar aparece {veces} veces; debe aparecer exactamente una.")
    copia = _copia_seguridad(ruta)
    nuevo = original.replace(buscar, args["reemplazar"], 1)
    _escribir_verificado(ruta, nuevo, "wb")
    return f"Editado y verificado: {ruta}. Copia previa: {copia}"


@herramienta(
    "mover",
    "Mueve o renombra un archivo o carpeta. No sobrescribe nada existente.",
    esquema({"origen": s("Ruta absoluta de origen"), "destino": s("Ruta absoluta de destino")}, ["origen", "destino"]),
    nivel=_nivel_doble,
    resumen=lambda e: f"Mover {e.get('origen')} → {e.get('destino')}",
)
async def mover(args):
    origen = rutas.para_escritura(args["origen"])
    destino = rutas.para_escritura(args["destino"])
    if not origen.exists():
        raise FileNotFoundError("El origen no existe.")
    if destino.exists():
        raise FileExistsError("El destino ya existe; no se sobrescribe.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.move, str(origen), str(destino))
    return f"Movido a {destino}"


@herramienta(
    "copiar",
    "Copia un archivo o carpeta. No sobrescribe nada existente.",
    esquema({"origen": s("Ruta absoluta de origen"), "destino": s("Ruta absoluta de destino")}, ["origen", "destino"]),
    nivel=_nivel_doble,
    resumen=lambda e: f"Copiar {e.get('origen')} → {e.get('destino')}",
)
async def copiar(args):
    origen = rutas.normalizar(args["origen"])
    destino = rutas.para_escritura(args["destino"])
    if not origen.exists():
        raise FileNotFoundError("El origen no existe.")
    if destino.exists():
        raise FileExistsError("El destino ya existe; no se sobrescribe.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        await asyncio.to_thread(shutil.copytree, origen, destino)
    else:
        await asyncio.to_thread(shutil.copy2, origen, destino)
    return f"Copiado a {destino}"


@herramienta(
    "enviar_a_papelera",
    "Envía un archivo o carpeta a la Papelera de reciclaje de Windows (recuperable).",
    esquema({"ruta": s("Ruta absoluta")}, ["ruta"]),
    nivel=2,
    resumen=lambda e: f"Enviar a la papelera: {e.get('ruta')}",
)
async def enviar_a_papelera(args):
    from send2trash import send2trash

    ruta = rutas.para_escritura(args["ruta"])
    if not ruta.exists():
        raise FileNotFoundError("No existe.")
    await asyncio.to_thread(send2trash, str(ruta))
    return f"Enviado a la papelera: {ruta}"
