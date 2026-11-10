"""Enlace entre las herramientas y la sesión viva (emisor de eventos y aprobaciones).

La sesión lo rellena al arrancar. Una herramienta que lo necesite y lo encuentre
vacío debe fallar cerrada.
"""

from typing import Any, Awaitable, Callable

emitir: Callable[[dict], Awaitable[None]] | None = None
aprobaciones: Any = None
