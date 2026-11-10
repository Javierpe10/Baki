"""Registro de herramientas de BAKI para el servidor MCP en proceso.

Cada herramienta declara su nivel:
- 1: se ejecuta sin preguntar (consultas, lecturas dentro de carpetas aprobadas).
- 2: BAKI muestra la llamada exacta y espera tu aprobación.
El nivel puede depender de los argumentos (por ejemplo, una lectura fuera de
las carpetas aprobadas sube a nivel 2).
"""

import json
import traceback
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from claude_agent_sdk import SdkMcpTool, tool

PREFIJO_MCP = "mcp__baki__"
MAX_SALIDA = 60_000

NivelFn = Callable[[dict, dict], int]


@dataclass
class Herramienta:
    nombre: str
    sdk: SdkMcpTool
    nivel: int | NivelFn
    resumen: Callable[[dict], str]

    def nivel_para(self, entrada: dict, config: dict) -> int:
        if callable(self.nivel):
            try:
                return int(self.nivel(entrada, config))
            except Exception:
                return 2  # ante la duda, pedir confirmación
        return self.nivel


REGISTRO: dict[str, Herramienta] = {}


class ErrorHerramienta(Exception):
    """Error esperado: su mensaje se devuelve tal cual a Claude."""


def texto(valor: Any) -> dict:
    if not isinstance(valor, str):
        valor = json.dumps(valor, ensure_ascii=False, indent=1, default=str)
    if len(valor) > MAX_SALIDA:
        valor = valor[:MAX_SALIDA] + f"\n…[recortado: {len(valor) - MAX_SALIDA} caracteres más]"
    return {"content": [{"type": "text", "text": valor}]}


def error(mensaje: str) -> dict:
    return {"content": [{"type": "text", "text": f"Error: {mensaje}"}], "is_error": True}


def _resumen_por_defecto(nombre: str) -> Callable[[dict], str]:
    def resumir(entrada: dict) -> str:
        cuerpo = json.dumps(entrada, ensure_ascii=False)
        return f"{nombre}: {cuerpo[:300]}"
    return resumir


def herramienta(
    nombre: str,
    descripcion: str,
    esquema: dict,
    nivel: int | NivelFn = 2,
    resumen: Callable[[dict], str] | None = None,
):
    """Registra una función async(args) -> resultado (str/dict/list)."""

    def decorar(fn: Callable[[dict], Awaitable[Any]]):
        async def envoltura(args: dict) -> dict:
            try:
                resultado = await fn(args or {})
            except (ErrorHerramienta, ValueError, FileNotFoundError,
                    FileExistsError, PermissionError, KeyError) as exc:
                mensaje = exc.args[0] if exc.args else type(exc).__name__
                return error(str(mensaje))
            except Exception as exc:  # no filtrar trazas con datos a Claude
                traceback.print_exc()
                return error(f"Fallo interno en {nombre}: {type(exc).__name__}")
            if isinstance(resultado, dict) and "content" in resultado:
                return resultado
            return texto(resultado)

        sdk_tool = tool(nombre, descripcion, esquema)(envoltura)
        REGISTRO[PREFIJO_MCP + nombre] = Herramienta(
            nombre=nombre,
            sdk=sdk_tool,
            nivel=nivel,
            resumen=resumen or _resumen_por_defecto(nombre),
        )
        return fn

    return decorar


def esquema(propiedades: dict, requeridos: list[str]) -> dict:
    return {
        "type": "object",
        "properties": propiedades,
        "required": requeridos,
        "additionalProperties": False,
    }


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}


def s(desc: str) -> dict:
    return {"type": "string", "description": desc}
