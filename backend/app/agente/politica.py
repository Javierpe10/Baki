"""Única puerta de permisos del agente.

Dos capas, ambas fail-closed:
1. Hook PreToolUse (se ejecuta siempre, incluso si la CLI ya habría permitido
   la herramienta): permite nivel 1, pide aprobación (ask) en nivel 2 y
   deniega todo lo que no esté en la política.
2. can_use_tool: recibe las llamadas marcadas como "ask", vuelve a evaluar la
   política y espera la decisión del usuario con los argumentos exactos.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.agente.registro import REGISTRO

PERMITIR = "allow"
PREGUNTAR = "ask"
DENEGAR = "deny"

# Herramientas integradas de Claude Code que no modifican nada.
INTEGRADAS_NIVEL_1 = {"WebSearch", "WebFetch", "ToolSearch", "TodoWrite", "Skill"}


@dataclass(frozen=True)
class Decision:
    accion: str
    motivo: str
    nivel: int = 0


def evaluar(nombre: str, entrada: Any, config: dict) -> Decision:
    if not isinstance(entrada, dict):
        return Decision(DENEGAR, "Argumentos no válidos.")
    if nombre in INTEGRADAS_NIVEL_1:
        return Decision(PERMITIR, "Nivel 1: consulta.", 1)
    herramienta = REGISTRO.get(nombre)
    if herramienta is None:
        return Decision(DENEGAR, f"La herramienta {nombre} no está permitida en BAKI.")
    nivel = herramienta.nivel_para(entrada, config)
    if nivel <= 1:
        return Decision(PERMITIR, "Nivel 1: sin confirmación.", 1)
    return Decision(PREGUNTAR, "Nivel 2: requiere tu aprobación.", 2)


def salida_hook(decision: Decision) -> dict:
    salida = {"hookEventName": "PreToolUse", "permissionDecision": decision.accion}
    if decision.accion != PERMITIR:
        salida["permissionDecisionReason"] = decision.motivo
    return {"hookSpecificOutput": salida}


def crear_hook(obtener_config: Callable[[], dict]):
    async def hook_pre_tool(input_data: dict, tool_use_id, context) -> dict:
        decision = evaluar(
            input_data.get("tool_name", ""),
            input_data.get("tool_input", {}),
            obtener_config(),
        )
        return salida_hook(decision)

    return hook_pre_tool


Aprobador = Callable[[str, dict], Awaitable[tuple[bool, str]]]


def crear_can_use_tool(obtener_config: Callable[[], dict], aprobador: Aprobador):
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    async def can_use_tool(nombre: str, entrada: dict, contexto) -> Any:
        decision = evaluar(nombre, entrada, obtener_config())
        if decision.accion == PERMITIR:
            return PermissionResultAllow()
        if decision.accion == DENEGAR:
            return PermissionResultDeny(message=decision.motivo)
        aprobado, motivo = await aprobador(nombre, entrada)
        if aprobado:
            return PermissionResultAllow()
        return PermissionResultDeny(message=motivo)

    return can_use_tool
