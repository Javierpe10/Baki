"""Control del ordenador: abrir cosas, PowerShell, portapapeles, información."""

import asyncio
import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from app.agente import rutas
from app.agente.registro import ErrorHerramienta, esquema, herramienta, s

EXTENSIONES_EJECUTABLES = {
    ".exe", ".bat", ".cmd", ".com", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf",
    ".wsh", ".msi", ".msp", ".scr", ".lnk", ".url", ".hta", ".cpl", ".reg", ".jar", ".py",
}

# Aplicaciones conocidas que se pueden abrir sin confirmación.
APPS = {
    "bloc de notas": "notepad.exe", "notepad": "notepad.exe",
    "calculadora": "calc.exe", "explorador": "explorer.exe",
    "chrome": "chrome", "edge": "msedge", "navegador": "msedge",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt", "outlook": "outlook",
    "vscode": "code", "visual studio code": "code", "terminal": "wt",
    "spotify": "spotify:", "whatsapp": "whatsapp:", "configuracion": "ms-settings:",
    "obsidian": "obsidian:",
}

MAX_SALIDA_PS = 30_000


def _nivel_abrir(entrada: dict, config: dict) -> int:
    objetivo = str(entrada.get("objetivo", "")).strip()
    bajo = objetivo.lower()
    if bajo.startswith(("http://", "https://")):
        return 1
    if bajo in APPS:
        return 1
    try:
        ruta = rutas.normalizar(objetivo)
    except Exception:
        return 2
    if rutas.es_protegida(ruta):
        return 2
    if ruta.is_dir():
        return 1
    if ruta.suffix.lower() in EXTENSIONES_EJECUTABLES:
        return 2
    return 1


@herramienta(
    "abrir",
    "Abre en el ordenador una web (URL), una carpeta, un documento con su programa, o una aplicación "
    "(bloc de notas, calculadora, chrome, edge, word, excel, powerpoint, outlook, vscode, spotify, whatsapp, "
    "obsidian, configuracion). Para otras aplicaciones indica la ruta del .exe.",
    esquema({"objetivo": s("URL, ruta absoluta o nombre de aplicación")}, ["objetivo"]),
    nivel=_nivel_abrir,
    resumen=lambda e: f"Abrir {e.get('objetivo')}",
)
async def abrir(args):
    objetivo = args["objetivo"].strip()
    bajo = objetivo.lower()
    if bajo in APPS:
        destino = APPS[bajo]
        if destino.endswith(":"):
            os.startfile(destino)
        else:
            subprocess.Popen(["cmd", "/c", "start", "", destino], creationflags=subprocess.CREATE_NO_WINDOW)
        return f"Abierto: {objetivo}"
    if bajo.startswith(("http://", "https://")):
        os.startfile(objetivo)
        return f"Abierta la web {objetivo}"
    ruta = rutas.normalizar(objetivo)
    if not ruta.exists():
        raise FileNotFoundError("No existe esa ruta.")
    os.startfile(str(ruta))
    return f"Abierto: {ruta}"


def _powershell(comando: str, carpeta: str | None, timeout: int) -> dict:
    exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
    proc = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + comando],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, cwd=carpeta or str(Path.home()),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    salida = (proc.stdout or "")[-MAX_SALIDA_PS:]
    errores = (proc.stderr or "")[-8000:]
    return {"codigo_salida": proc.returncode, "salida": salida, "errores": errores}


@herramienta(
    "ejecutar_powershell",
    "Ejecuta un comando de PowerShell en el ordenador del usuario y devuelve su salida. "
    "Úsalo para lo que no cubran otras herramientas (instalar con winget, comprimir, procesos, "
    "red, git, scripts). Siempre pide aprobación: explica el motivo en una frase.",
    esquema({
        "comando": s("Comando de PowerShell completo"),
        "motivo": s("Para qué sirve, en una frase"),
        "carpeta": s("Carpeta de trabajo opcional (ruta absoluta)"),
    }, ["comando", "motivo"]),
    nivel=2,
    resumen=lambda e: f"PowerShell ({e.get('motivo', '')}):\n{e.get('comando', '')}",
)
async def ejecutar_powershell(args):
    carpeta = args.get("carpeta")
    if carpeta:
        carpeta = str(rutas.normalizar(carpeta))
    try:
        return await asyncio.to_thread(_powershell, args["comando"], carpeta, 180)
    except subprocess.TimeoutExpired:
        raise ErrorHerramienta("El comando superó 3 minutos y se detuvo.")


@herramienta(
    "leer_portapapeles",
    "Devuelve el texto que hay ahora en el portapapeles.",
    esquema({}, []),
    nivel=1,
    resumen=lambda e: "Leer el portapapeles",
)
async def leer_portapapeles(args):
    r = await asyncio.to_thread(_powershell, "Get-Clipboard -Raw", None, 15)
    return r["salida"] or "(portapapeles vacío)"


@herramienta(
    "copiar_al_portapapeles",
    "Copia un texto al portapapeles para que el usuario lo pegue.",
    esquema({"texto": s("Texto a copiar")}, ["texto"]),
    nivel=1,
    resumen=lambda e: "Copiar texto al portapapeles",
)
async def copiar_al_portapapeles(args):
    def _copiar():
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
            input=args["texto"], text=True, encoding="utf-8", timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    await asyncio.to_thread(_copiar)
    return "Copiado al portapapeles."


@herramienta(
    "info_sistema",
    "Fecha y hora local, usuario, equipo, sistema operativo y espacio libre en disco.",
    esquema({}, []),
    nivel=1,
    resumen=lambda e: "Consultar información del sistema",
)
async def info_sistema(args):
    total, usado, libre = shutil.disk_usage(Path.home().anchor)
    return {
        "fecha_hora_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "usuario": os.environ.get("USERNAME"),
        "equipo": platform.node(),
        "sistema": platform.platform(),
        "carpeta_usuario": str(Path.home()),
        "disco_libre_gb": round(libre / 1e9, 1),
        "disco_total_gb": round(total / 1e9, 1),
    }
