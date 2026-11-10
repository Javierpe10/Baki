"""Validación de rutas para las herramientas del agente.

Reglas:
- Solo rutas absolutas (una relativa se resolvería contra un cwd imprevisible).
- Sin enlaces simbólicos ni junctions en la ruta (podrían saltar fuera).
- Zonas protegidas: nunca se escriben y su lectura siempre pide confirmación
  (credenciales, claves SSH, configuración de Claude y el propio código de BAKI,
  para que el agente no pueda reescribir su propia política de permisos).
"""

import os
from pathlib import Path
from typing import Iterable

from app.agente.config import BACKEND_DIR, DATA_DIR, HOME, PROJECT_ROOT
from app.permissions import PermissionManager

# Carpetas cuyo contenido el agente nunca puede modificar.
ZONAS_PROTEGIDAS = [
    BACKEND_DIR / "app",
    BACKEND_DIR / "tests",
    # Configuración, auditoría, skills y sesión de BAKI: el agente no puede
    # ampliarse permisos editando su propia configuración.
    DATA_DIR,
    PROJECT_ROOT / ".venv",
    HOME / ".ssh",
    HOME / ".aws",
    HOME / ".gnupg",
    HOME / ".claude",
    HOME / ".claude.json",
    HOME / "AppData" / "Roaming" / "Microsoft" / "Credentials",
    HOME / "AppData" / "Local" / "Microsoft" / "Credentials",
    HOME / "AppData" / "Roaming" / "Microsoft" / "Protect",
    Path(os.environ.get("SystemRoot", r"C:\Windows")),
]

# Nombres de archivo que suelen contener secretos.
NOMBRES_SENSIBLES = {".env", "id_rsa", "id_ed25519", "credentials.json", "token.json"}
SUFIJOS_SENSIBLES = {".pem", ".key", ".pfx", ".p12", ".kdbx"}


class RutaNoValida(ValueError):
    pass


def normalizar(ruta) -> Path:
    if not isinstance(ruta, str) or not ruta.strip():
        raise RutaNoValida("Ruta vacía o no válida.")
    candidata = Path(os.path.expandvars(os.path.expanduser(ruta.strip().strip('"'))))
    if not candidata.is_absolute():
        raise RutaNoValida(
            "La ruta debe ser absoluta, por ejemplo C:\\Users\\<usuario>\\Desktop\\archivo.txt."
        )
    absoluta = Path(os.path.abspath(candidata))
    if PermissionManager._contains_reparse_point(absoluta):
        raise RutaNoValida("No se permiten rutas con enlaces simbólicos o junctions.")
    return absoluta.resolve(strict=False)


def _dentro(ruta: Path, base: Path) -> bool:
    try:
        base_resuelta = base.resolve(strict=False)
    except OSError:
        return False
    return ruta == base_resuelta or ruta.is_relative_to(base_resuelta)


def es_protegida(ruta: Path) -> bool:
    if ruta.name.lower() in NOMBRES_SENSIBLES or ruta.suffix.lower() in SUFIJOS_SENSIBLES:
        return True
    return any(_dentro(ruta, zona) for zona in ZONAS_PROTEGIDAS)


def en_carpetas_aprobadas(ruta: Path, carpetas: Iterable[str]) -> bool:
    return any(_dentro(ruta, Path(c)) for c in carpetas if c)


def segura_en_aprobadas(ruta, carpetas: Iterable[str]) -> bool:
    """True si la ruta es válida, no protegida y cae dentro de una carpeta aprobada."""
    try:
        r = normalizar(ruta)
    except (RutaNoValida, OSError):
        return False
    return not es_protegida(r) and en_carpetas_aprobadas(r, carpetas)


def para_escritura(ruta) -> Path:
    r = normalizar(ruta)
    if es_protegida(r):
        raise RutaNoValida("Esa ruta está protegida: BAKI no puede modificarla.")
    return r
