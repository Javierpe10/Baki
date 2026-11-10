"""Subagente programador: Claude Code trabajando dentro de UNA carpeta de proyecto.

- Tú apruebas la tarea una vez (carpeta + instrucción).
- Dentro de esa carpeta puede leer, crear y editar archivos sin preguntar.
- Fuera de ella no puede leer ni escribir.
- Cada comando de terminal pide aprobación; puedes aprobar «todos los de esta tarea».
- No carga configuración del proyecto (.claude/settings.json, hooks) del repositorio:
  un repositorio clonado no puede inyectarle permisos ni comandos.
"""

import uuid
from pathlib import Path

from app.agente import config as cfg
from app.agente import contexto, rutas
from app.agente.registro import ErrorHerramienta, esquema, herramienta, s

PERMITIR, PREGUNTAR, DENEGAR = "allow", "ask", "deny"
LECTURA = {"Read", "Glob", "Grep", "NotebookRead"}
ESCRITURA = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
LIBRES = {"WebSearch", "WebFetch", "Skill", "TodoWrite", "ToolSearch"}
COMANDOS = {"Bash", "PowerShell"}

PROMPT = """Eres el programador de BAKI. Trabajas solo dentro de la carpeta {carpeta}.
Usa rutas dentro de esa carpeta. No intentes leer ni escribir fuera: se bloqueará.
Método: entiende lo que hay, planifica con TodoWrite, trabaja en pasos pequeños y verificables.
Si hay lógica de negocio, usa la skill baki:tdd (test primero). Si existe SPEC.md o tasks/plan.md, síguelos.
Si algo falla, usa baki:debugging-and-error-recovery. Si el código toca entradas externas, datos personales,
autenticación, webhooks o llamadas a LLM, aplica baki:security-and-hardening antes de terminar. Revisa tu propio código al terminar
(léelo otra vez, ejecuta tests, linters o la app). Cada comando de terminal lo aprueba Javier: agrupa
comandos y explica para qué sirve cada uno. Nunca guardes claves en el código: usa variables de entorno
y un .env.example. Si algo no se puede hacer, dilo claramente.
Al terminar, responde en español con: qué has construido, cómo arrancarlo, qué está probado y qué falta."""


def carpeta_valida(ruta: str) -> Path:
    carpeta = rutas.para_escritura(ruta)
    if len(carpeta.parts) < 4 or carpeta in (Path.home(), Path.home() / "Desktop", Path.home() / "Documents"):
        raise ErrorHerramienta("Indica una carpeta de proyecto concreta, no una carpeta raíz del usuario.")
    return carpeta


def _ruta_de(nombre: str, entrada: dict) -> str | None:
    if nombre in ("Read", "Write", "Edit", "MultiEdit"):
        return entrada.get("file_path")
    if nombre in ("NotebookEdit", "NotebookRead"):
        return entrada.get("notebook_path")
    return entrada.get("path")


def evaluar_programador(nombre: str, entrada: dict, carpeta: Path) -> str:
    if not isinstance(entrada, dict):
        return DENEGAR
    if nombre in LIBRES:
        return PERMITIR
    if nombre in COMANDOS:
        return PREGUNTAR
    if nombre in LECTURA or nombre in ESCRITURA:
        ruta = _ruta_de(nombre, entrada)
        if ruta is None and nombre in ("Glob", "Grep"):
            return PERMITIR  # por defecto buscan en el cwd, que es la carpeta
        try:
            destino = rutas.normalizar(ruta)
        except Exception:
            return DENEGAR
        if rutas.es_protegida(destino) or not rutas.en_carpetas_aprobadas(destino, [str(carpeta)]):
            return DENEGAR
        return PERMITIR
    return DENEGAR


async def _ejecutar(carpeta: Path, instruccion: str, emitir, aprobaciones, grupo: str) -> dict:
    from claude_agent_sdk import (
        AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher,
        PermissionResultAllow, PermissionResultDeny, ResultMessage, ToolUseBlock,
    )

    archivos: set[str] = set()

    async def hook(input_data, tool_use_id, ctx):
        nombre = input_data.get("tool_name", "")
        entrada = input_data.get("tool_input", {})
        decision = evaluar_programador(nombre, entrada, carpeta)
        salida = {"hookEventName": "PreToolUse", "permissionDecision": decision}
        if decision == DENEGAR:
            salida["permissionDecisionReason"] = f"Bloqueado: solo puedes trabajar dentro de {carpeta}."
        return {"hookSpecificOutput": salida}

    async def can_use(nombre, entrada, ctx):
        decision = evaluar_programador(nombre, entrada, carpeta)
        if decision == PERMITIR:
            return PermissionResultAllow()
        if decision == DENEGAR:
            return PermissionResultDeny(message=f"Bloqueado: solo puedes trabajar dentro de {carpeta}.")
        ok, motivo = await aprobaciones.solicitar(
            f"programador:{nombre}", entrada, grupo=grupo, etiqueta_grupo=f"tarea en {carpeta.name}",
        )
        return PermissionResultAllow() if ok else PermissionResultDeny(message=motivo or "Rechazado por el usuario.")

    config = cfg.cargar()
    opciones = ClaudeAgentOptions(
        model=config["modelo"],
        effort=config.get("esfuerzo") or None,
        system_prompt=PROMPT.format(carpeta=carpeta),
        setting_sources=[],
        plugins=[{"type": "local", "path": str(cfg.PLUGIN_DIR)}],
        strict_mcp_config=True,
        tools=sorted(LECTURA | ESCRITURA | LIBRES | {"Bash"}),
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[hook], timeout=30)]},
        can_use_tool=can_use,
        permission_mode="default",
        max_turns=int(config.get("max_turnos_programador", 80)),
        cwd=str(carpeta),
    )
    informe, coste, error = "", None, False
    async with ClaudeSDKClient(opciones) as cliente:
        await cliente.query(instruccion)
        async for msg in cliente.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, ToolUseBlock):
                        if b.name in ESCRITURA and isinstance(b.input, dict):
                            ruta = _ruta_de(b.name, b.input)
                            if ruta:
                                archivos.add(ruta)
                        if emitir:
                            detalle = b.input.get("command") or _ruta_de(b.name, b.input) or b.input.get("pattern") or ""
                            await emitir({"type": "herramienta", "nombre": f"programador · {b.name}",
                                          "resumen": str(detalle)[:300], "nivel": 2 if b.name in COMANDOS else 1})
            elif isinstance(msg, ResultMessage):
                informe, coste, error = msg.result or "", msg.total_cost_usd, msg.is_error
    return {"carpeta": str(carpeta), "terminado_con_error": error, "informe": informe,
            "archivos_escritos": sorted(archivos)[:200], "coste_equivalente_usd": coste}


@herramienta(
    "programar_proyecto",
    "Lanza un programador experto (Claude Code) que construye o modifica código dentro de UNA carpeta de proyecto: "
    "crea la estructura, escribe código y tests, ejecuta comandos (con aprobación) y revisa su trabajo. "
    "Pásale una instrucción completa y autosuficiente (objetivo, tecnología, requisitos, criterios de terminado). "
    "Puede tardar varios minutos. Carpeta habitual: Escritorio\\Proyectos\\<nombre> (ver carpeta_proyectos).",
    esquema({
        "carpeta": s("Ruta absoluta de la carpeta del proyecto (se crea si no existe)"),
        "instruccion": s("Encargo completo para el programador"),
    }, ["carpeta", "instruccion"]),
    nivel=2,
    resumen=lambda e: (f"Programador en {e.get('carpeta')} (podrá crear y editar archivos SOLO ahí; "
                       f"cada comando te lo pedirá):\n\n{e.get('instruccion', '')[:1800]}"),
)
async def programar_proyecto(args):
    if contexto.aprobaciones is None:
        raise ErrorHerramienta("El programador solo funciona en una sesión interactiva de BAKI.")
    carpeta = carpeta_valida(args["carpeta"])
    carpeta.mkdir(parents=True, exist_ok=True)
    grupo = uuid.uuid4().hex
    try:
        return await _ejecutar(carpeta, args["instruccion"], contexto.emitir, contexto.aprobaciones, grupo)
    finally:
        contexto.aprobaciones.cerrar_grupo(grupo)
