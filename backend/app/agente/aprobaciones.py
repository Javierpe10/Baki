"""Cola de aprobaciones del agente.

Cada llamada de nivel 2 crea una solicitud con los argumentos exactos y su
huella SHA-256. El agente queda esperando hasta que el usuario aprueba o
rechaza, o hasta que caduca (rechazo). Cada solicitud se resuelve una sola vez.
"""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from app.agente.registro import REGISTRO, PREFIJO_MCP

ESPERA_MAXIMA_S = 300


def huella(nombre: str, entrada: dict) -> str:
    canonico = json.dumps(
        {"tool": nombre, "input": entrada},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def resumir(nombre: str, entrada: dict) -> str:
    if nombre.startswith("programador:"):
        herramienta = nombre.split(":", 1)[1]
        detalle = entrada.get("description") or ""
        cabecera = f"Comando del programador ({herramienta})" + (f": {detalle}" if detalle else "")
        return f"{cabecera}\n{entrada.get('command', entrada)}"
    herramienta = REGISTRO.get(nombre)
    if herramienta:
        try:
            return herramienta.resumen(entrada)
        except Exception:
            pass
    return f"{nombre.removeprefix(PREFIJO_MCP)}"


class GestorAprobaciones:
    def __init__(
        self,
        audit_path: Path,
        notificar: Callable[[dict], Awaitable[None]] | None = None,
        espera_maxima: float = ESPERA_MAXIMA_S,
    ):
        self.audit_path = audit_path
        self.notificar = notificar
        self.espera_maxima = espera_maxima
        self.pendientes: dict[str, dict] = {}
        self._futuros: dict[str, asyncio.Future] = {}
        # Grupos (p. ej. una tarea de programación) cuyos comandos el usuario
        # aprobó en bloque. Se cierran al terminar la tarea.
        self.grupos_aprobados: set[str] = set()

    def _auditar(self, solicitud: dict, evento: str) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        linea = {
            "id": solicitud["id"],
            "herramienta": solicitud["herramienta"],
            "resumen": solicitud["resumen"][:500],
            "huella": solicitud["huella"],
            "evento": evento,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def publicas(self) -> list[dict]:
        return [dict(s) for s in self.pendientes.values()]

    async def solicitar(
        self, nombre: str, entrada: dict, grupo: str | None = None, etiqueta_grupo: str | None = None,
    ) -> tuple[bool, str]:
        solicitud = {
            "id": str(uuid.uuid4()),
            "herramienta": nombre.removeprefix(PREFIJO_MCP),
            "resumen": resumir(nombre, entrada),
            "argumentos": entrada,
            "huella": huella(nombre, entrada),
            "creada": datetime.now(timezone.utc).isoformat(),
            "caduca_en_s": self.espera_maxima,
            "grupo": grupo,
            "etiqueta_grupo": etiqueta_grupo,
        }
        if grupo and grupo in self.grupos_aprobados:
            self._auditar(solicitud, "aprobada_por_grupo")
            return True, ""
        # Si no se puede auditar, no se pide ni se ejecuta nada.
        self._auditar(solicitud, "solicitada")
        futuro = asyncio.get_running_loop().create_future()
        self.pendientes[solicitud["id"]] = solicitud
        self._futuros[solicitud["id"]] = futuro
        if self.notificar:
            await self.notificar({"type": "aprobacion", "solicitud": solicitud})
        try:
            aprobado = await asyncio.wait_for(futuro, timeout=self.espera_maxima)
        except asyncio.TimeoutError:
            aprobado = None
        except asyncio.CancelledError:
            aprobado = False
        finally:
            self.pendientes.pop(solicitud["id"], None)
            self._futuros.pop(solicitud["id"], None)
        if aprobado is None:
            self._auditar(solicitud, "caducada")
            mensaje = "La solicitud caducó sin respuesta del usuario. No se ha ejecutado."
        elif aprobado:
            self._auditar(solicitud, "aprobada")
            mensaje = ""
        else:
            self._auditar(solicitud, "rechazada")
            mensaje = "El usuario ha rechazado esta acción. No se ha ejecutado; no insistas salvo que lo pida."
        if self.notificar:
            await self.notificar({
                "type": "aprobacion_resuelta",
                "id": solicitud["id"],
                "aprobado": bool(aprobado),
            })
        return bool(aprobado), mensaje

    def resolver(self, solicitud_id: str, aprobado: bool, todo_el_grupo: bool = False) -> bool:
        futuro = self._futuros.get(solicitud_id)
        if futuro is None or futuro.done():
            return False
        grupo = (self.pendientes.get(solicitud_id) or {}).get("grupo")
        if aprobado and todo_el_grupo and grupo:
            self.grupos_aprobados.add(grupo)
            # Aprobar también lo que ya estaba esperando del mismo grupo.
            for sid, s in list(self.pendientes.items()):
                if sid != solicitud_id and s.get("grupo") == grupo:
                    f = self._futuros.get(sid)
                    if f is not None and not f.done():
                        f.set_result(True)
        futuro.set_result(bool(aprobado))
        return True

    def cerrar_grupo(self, grupo: str) -> None:
        self.grupos_aprobados.discard(grupo)
        for sid, s in list(self.pendientes.items()):
            if s.get("grupo") == grupo:
                self.resolver(sid, False)

    def rechazar_todas(self) -> None:
        self.grupos_aprobados.clear()
        for sid in list(self._futuros):
            self.resolver(sid, False)
