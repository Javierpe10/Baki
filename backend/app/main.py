
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.claude_gateway import ClaudeGateway
from app.permissions import PermissionManager
from app.file_tools import FileTools
from app.tool_registry import ToolRegistry
from app.tool_executor import ToolExecutor


@asynccontextmanager
async def lifespan(_app):
    from app.agente.sesion import planificador

    tarea = asyncio.create_task(planificador(difundir))
    yield
    tarea.cancel()
    if agente_global is not None:
        await agente_global.cerrar()


app = FastAPI(
    title="BAKI",
    description="Local AI Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

# Cabecera que solo puede enviar el frontend de BAKI.
# Una petición cross-origin con esta cabecera requiere preflight CORS,
# que solo admite http://localhost:5173. Esto protege frente a páginas web
# abiertas en el mismo navegador, pero NO frente a DNS rebinding: una página
# maliciosa que resuelve a 127.0.0.1 es same-origin y puede añadir la cabecera.
# Por eso también se valida Host (frente a rebinding) y Origin.
# NO protege frente a procesos locales maliciosos.
HOSTS_PERMITIDOS = {"127.0.0.1:8001", "localhost:8001"}
ORIGENES_PERMITIDOS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
}


def require_action_header(
    request: Request,
    x_baki_action: str | None = Header(default=None),
):
    if x_baki_action != "1":
        raise HTTPException(status_code=403, detail="Petición no autorizada.")
    if request.headers.get("host") not in HOSTS_PERMITIDOS:
        raise HTTPException(status_code=403, detail="Petición no autorizada.")
    origin = request.headers.get("origin")
    if origin is not None and origin not in ORIGENES_PERMITIDOS:
        raise HTTPException(status_code=403, detail="Petición no autorizada.")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VAULT_PATH = PROJECT_ROOT / "knowledge" / "BAKI Knowledge"


# --------------------------------------------------
# COMPONENTES PRINCIPALES
# --------------------------------------------------

claude = ClaudeGateway()

permissions = PermissionManager(str(VAULT_PATH))

file_tools = FileTools(permissions)

tool_registry = ToolRegistry()

tool_executor = ToolExecutor(
    registry=tool_registry,
    permissions=permissions,
)


# --------------------------------------------------
# REGISTRO DE HERRAMIENTAS
# --------------------------------------------------

tool_registry.register(
    name="create_file",
    description="Crear un archivo nuevo en el sistema.",
    handler=file_tools._create_file_authorized,
    argument_types={
        "path": str,
        "content": str,
    },
    required_arguments={
        "path",
        "content",
    },
    resource_type="file",
    operation="create",
    resource_id_argument="path",
)

tool_registry.register(
    name="read_file",
    description="Leer el contenido de un archivo de texto.",
    handler=file_tools._read_file_authorized,
    argument_types={"path": str},
    required_arguments={"path"},
    resource_type="file",
    operation="read",
    resource_id_argument="path",
)

tool_registry.register(
    name="list_dir",
    description="Listar los nombres de una carpeta, sin leer su contenido.",
    handler=file_tools._list_dir_authorized,
    argument_types={"path": str},
    required_arguments={"path"},
    resource_type="folder",
    operation="list",
    resource_id_argument="path",
)


# --------------------------------------------------
# MODELOS
# --------------------------------------------------

class ChatRequest(BaseModel):
    message: str


# --------------------------------------------------
# HEALTH
# --------------------------------------------------

@app.get("/health")
def health():
    return {"status": "BAKI online"}


# --------------------------------------------------
# CHAT
# --------------------------------------------------

@app.post("/chat", dependencies=[Depends(require_action_header)])
def chat(request: ChatRequest):
    try:
        plan = claude.plan(request.message)

        if plan["type"] == "message":
            return {
                "response": plan["content"]
            }

        if plan["type"] == "create_file":
            tool_name = "create_file"
            arguments = {
                "path": plan["path"],
                "content": plan["content"],
            }

        elif plan["type"] == "read_file":
            tool_name = "read_file"
            arguments = {"path": plan["path"]}

        elif plan["type"] == "list_dir":
            tool_name = "list_dir"
            arguments = {"path": plan["path"]}

        else:
            return {
                "response": "No he podido procesar la operación."
            }

        result = tool_executor.execute(
            tool_name=tool_name,
            arguments=arguments,
            context=request.message,
        )

        if result["status"] == "authorization_required":
            return {
                "response": (
                    "He preparado la operación. "
                    "Necesito tu autorización antes de ejecutarla."
                ),
                "authorization_required": True,
                "request": result["request"],
            }

        return {
            "response": "No he podido procesar la operación."
        }

    except (ValueError, FileExistsError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# --------------------------------------------------
# PERMISOS
# --------------------------------------------------

@app.get("/permissions/pending", dependencies=[Depends(require_action_header)])
def pending_permissions():
    return [
        request.copy()
        for request in permissions.pending_requests.values()
        if request["status"] == "pending"
    ]


@app.post("/permissions/{request_id}/approve", dependencies=[Depends(require_action_header)])
def approve_permission(request_id: str):
    try:
        return permissions.approve(request_id)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/permissions/{request_id}/deny", dependencies=[Depends(require_action_header)])
def deny_permission(request_id: str):
    try:
        result = permissions.deny(request_id)

        tool_executor.pending_executions.pop(request_id, None)

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


# --------------------------------------------------
# EJECUCIÓN DE OPERACIONES AUTORIZADAS
# --------------------------------------------------

@app.post("/tools/files/execute/{request_id}", dependencies=[Depends(require_action_header)])
def execute_approved_file(request_id: str):

    # Comprobación fuera del try: un HTTPException dentro se convertiría en 500.
    pending = tool_executor.pending_executions.get(request_id)

    if pending is None:
        raise HTTPException(
            status_code=400,
            detail="No existe una operación pendiente para esta solicitud.",
        )

    original_prompt = pending.context

    try:

        execution = tool_executor.execute_approved(request_id)

        if execution["status"] != "success":
            return execution

        result = execution["result"]

        print(
            "CONTEXTO ORIGINAL:",
            repr(original_prompt),
            flush=True,
        )

        # Continuar la conversación con Claude.
        if original_prompt:

            try:
                response = claude.continue_after_tool(
                    original_prompt=original_prompt,
                    tool_name=pending.tool_name,
                    tool_result=result,
                )

                result["response"] = response

            except Exception as error:

                print(
                    "ERROR CONTINUANDO CON CLAUDE:",
                    repr(error),
                    flush=True,
                )

                result["response"] = (
                    f"El archivo se ha creado correctamente en "
                    f"{result['path']}, pero ha fallado la respuesta "
                    f"de Claude: {error}"
                )

        print(
            "RESPUESTA FINAL CLAUDE:",
            repr(result.get("response")),
            flush=True,
        )

        return result

    except (ValueError, FileExistsError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ==================================================
# AGENTE BAKI (Claude Agent SDK) — WebSocket /ws
# ==================================================

clientes_ws: set[WebSocket] = set()
agente_global = None
# Solo una ventana habla en voz alta: la última desde la que el usuario habló o
# escribió. Las demás muestran el texto pero no lo leen (evita voces solapadas).
cliente_voz: WebSocket | None = None


async def difundir(evento: dict) -> None:
    global cliente_voz
    if cliente_voz not in clientes_ws:
        cliente_voz = next(iter(clientes_ws), None)
    for ws in list(clientes_ws):
        try:
            await ws.send_json({**evento, "hablar": ws is cliente_voz})
        except Exception:
            clientes_ws.discard(ws)


def obtener_agente():
    global agente_global
    if agente_global is None:
        from app.agente.sesion import Agente

        agente_global = Agente(difundir)
    return agente_global


def _ws_autorizado(ws: WebSocket) -> bool:
    return (
        ws.headers.get("host") in HOSTS_PERMITIDOS
        and ws.headers.get("origin") in ORIGENES_PERMITIDOS
    )


@app.websocket("/ws")
async def websocket_agente(ws: WebSocket):
    if not _ws_autorizado(ws):
        await ws.close(code=1008)
        return
    global cliente_voz
    await ws.accept()
    clientes_ws.add(ws)
    cliente_voz = ws
    agente = obtener_agente()
    await ws.send_json({
        "type": "hola",
        "pendientes": agente.aprobaciones.publicas(),
        "ocupado": agente.ocupado,
    })
    tareas: set[asyncio.Task] = set()
    try:
        while True:
            datos = await ws.receive_json()
            tipo = datos.get("type")
            if tipo in ("mensaje", "aprobar", "rechazar", "interrumpir", "nueva_conversacion"):
                cliente_voz = ws
            if tipo == "mensaje":
                texto = str(datos.get("texto", "")).strip()[:20000]
                if texto:
                    t = asyncio.create_task(agente.preguntar(texto))
                    tareas.add(t)
                    t.add_done_callback(tareas.discard)
            elif tipo == "aprobar":
                agente.aprobaciones.resolver(
                    str(datos.get("id")), True, todo_el_grupo=bool(datos.get("grupo"))
                )
            elif tipo == "rechazar":
                agente.aprobaciones.resolver(str(datos.get("id")), False)
            elif tipo == "interrumpir":
                await agente.interrumpir()
            elif tipo == "nueva_conversacion":
                await agente.nueva_conversacion()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        clientes_ws.discard(ws)


class TtsRequest(BaseModel):
    texto: str


@app.post("/tts", dependencies=[Depends(require_action_header)])
async def tts(request: TtsRequest):
    from app.integraciones.tts import sintetizar

    audio = await sintetizar(request.texto)
    if audio is None:
        return Response(status_code=204)
    datos, tipo = audio
    return Response(content=datos, media_type=tipo)


@app.get("/estado", dependencies=[Depends(require_action_header)])
def estado():
    from app.agente import config as cfg
    from app.agente.sesion import estado_integraciones
    from app.integraciones.tts import proveedor

    c = cfg.cargar()
    return {
        "modelo": c["modelo"],
        "esfuerzo": c.get("esfuerzo"),
        "voz": proveedor(),
        "palabra_activacion": c.get("palabra_activacion", "baki"),
        "integraciones": estado_integraciones(),
        "carpetas_aprobadas": c["carpetas_aprobadas"],
    }


class ConfigRequest(BaseModel):
    modelo: str | None = None
    esfuerzo: str | None = None


MODELOS_PERMITIDOS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5", "claude-fable-5-1"}
ESFUERZOS_PERMITIDOS = {"low", "medium", "high", "xhigh", "max"}


@app.post("/config", dependencies=[Depends(require_action_header)])
async def cambiar_config(request: ConfigRequest):
    from app.agente import config as cfg

    cambios = {}
    if request.modelo:
        if request.modelo not in MODELOS_PERMITIDOS:
            raise HTTPException(status_code=400, detail="Modelo no permitido.")
        cambios["modelo"] = request.modelo
    if request.esfuerzo:
        if request.esfuerzo not in ESFUERZOS_PERMITIDOS:
            raise HTTPException(status_code=400, detail="Esfuerzo no válido.")
        cambios["esfuerzo"] = request.esfuerzo
    cfg.guardar(cambios)
    await obtener_agente().recargar()
    return {"ok": True, **cambios}


# --------------------------------------------------
# PANELES DE LA INTERFAZ (solo lectura, salvo abrir conversación)
# --------------------------------------------------

@app.get("/skills", dependencies=[Depends(require_action_header)])
def skills():
    from app.agente.panel import listar_skills

    return listar_skills()


@app.get("/conversaciones", dependencies=[Depends(require_action_header)])
def conversaciones():
    from app.agente.panel import listar_conversaciones

    return {"actual": obtener_agente().session_id, "lista": listar_conversaciones()}


@app.get("/conversaciones/{session_id}", dependencies=[Depends(require_action_header)])
def conversacion(session_id: str):
    from app.agente.panel import mensajes_conversacion

    try:
        return mensajes_conversacion(session_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/conversaciones/{session_id}/abrir", dependencies=[Depends(require_action_header)])
async def abrir_conversacion(session_id: str):
    from app.agente.panel import listar_conversaciones, valido

    if not valido(session_id) or session_id not in {c["id"] for c in listar_conversaciones(500)}:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    await obtener_agente().abrir_conversacion(session_id)
    return {"ok": True, "actual": session_id}


class RenombrarRequest(BaseModel):
    titulo: str


@app.post("/conversaciones/{session_id}/renombrar", dependencies=[Depends(require_action_header)])
def renombrar_conversacion(session_id: str, request: RenombrarRequest):
    from app.agente.panel import renombrar_conversacion as renombrar

    try:
        return {"ok": True, "titulo": renombrar(session_id, request.titulo)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.get("/uso", dependencies=[Depends(require_action_header)])
async def uso():
    return await obtener_agente().uso()


@app.get("/tareas", dependencies=[Depends(require_action_header)])
def tareas():
    from app.agente.herramientas import rutinas as rut

    agente = obtener_agente()
    return {
        "trabajando": agente.ocupado,
        "pendientes": agente.aprobaciones.publicas(),
        "rutinas": rut.cargar(),
    }


# --------------------------------------------------
# INTERFAZ COMPILADA (npm run build) servida en :8001
# --------------------------------------------------

DIST = PROJECT_ROOT / "frontend" / "dist"

if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/")
def interfaz():
    indice = DIST / "index.html"
    if not indice.is_file():
        raise HTTPException(status_code=404, detail="Interfaz no compilada. Ejecuta npm run build en frontend.")
    # Sin caché: tras actualizar BAKI, la ventana carga siempre la interfaz nueva.
    return FileResponse(indice, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/favicon.svg")
def favicon():
    return FileResponse(DIST / "favicon.svg")
