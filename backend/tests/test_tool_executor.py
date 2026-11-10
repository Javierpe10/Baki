"""Pruebas del ciclo de autorización: ToolExecutor + PermissionManager + create_file.

Ejecutar desde la carpeta backend:
    ..\\.venv\\Scripts\\python.exe -m pytest tests -q
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.file_tools import FileTools
from app.permissions import PermissionManager
from app.tool_executor import ToolExecutor
from app.tool_registry import ToolRegistry


CONTENIDO = "contenido de prueba"


@pytest.fixture
def entorno(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    destino = tmp_path / "destino"
    destino.mkdir()

    permisos = PermissionManager(
        str(vault),
        audit_path=str(tmp_path / "audit.jsonl"),
    )
    file_tools = FileTools(permisos)

    registro = ToolRegistry()
    registro.register(
        name="create_file",
        description="Crear un archivo nuevo en el sistema.",
        handler=file_tools._create_file_authorized,
        argument_types={"path": str, "content": str},
        required_arguments={"path", "content"},
        resource_type="file",
        operation="create",
        resource_id_argument="path",
    )

    ejecutor = ToolExecutor(registry=registro, permissions=permisos)

    return SimpleNamespace(
        vault=vault,
        destino=destino,
        permisos=permisos,
        ejecutor=ejecutor,
        ruta=str(destino / "nuevo.txt"),
    )


def _solicitar(entorno):
    """Crea una solicitud pendiente y devuelve su identificador."""
    resultado = entorno.ejecutor.execute(
        "create_file",
        {"path": entorno.ruta, "content": CONTENIDO},
    )
    assert resultado["status"] == "authorization_required"
    return resultado["request"]["id"]


def _aprobar(entorno, request_id):
    entorno.permisos.approve(request_id)


# ---------------------------------------------------------------
# Flujo feliz
# ---------------------------------------------------------------

def test_sin_aprobacion_no_se_crea_archivo(entorno):
    _solicitar(entorno)

    assert not (entorno.destino / "nuevo.txt").exists()


def test_aprobado_crea_el_archivo_con_el_contenido_exacto(entorno):
    request_id = _solicitar(entorno)
    _aprobar(entorno, request_id)

    resultado = entorno.ejecutor.execute_approved(request_id)

    assert resultado["status"] == "success"
    assert (entorno.destino / "nuevo.txt").read_text(encoding="utf-8") == CONTENIDO


def test_la_misma_aprobacion_no_se_puede_ejecutar_dos_veces(entorno):
    request_id = _solicitar(entorno)
    _aprobar(entorno, request_id)
    entorno.ejecutor.execute_approved(request_id)

    with pytest.raises(ValueError):
        entorno.ejecutor.execute_approved(request_id)


# ---------------------------------------------------------------
# Denegación y caducidad
# ---------------------------------------------------------------

def test_denegada_no_crea_archivo(entorno):
    request_id = _solicitar(entorno)
    entorno.permisos.deny(request_id)

    resultado = entorno.ejecutor.execute_approved(request_id)

    assert resultado["status"] == "authorization_required"
    assert not (entorno.destino / "nuevo.txt").exists()


def test_no_se_puede_aprobar_una_solicitud_caducada(entorno):
    request_id = _solicitar(entorno)
    entorno.permisos.pending_requests[request_id]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()

    with pytest.raises(ValueError):
        _aprobar(entorno, request_id)


def test_aprobacion_caducada_no_permite_ejecutar(entorno):
    request_id = _solicitar(entorno)
    _aprobar(entorno, request_id)
    entorno.permisos.pending_requests[request_id]["approval_expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()

    resultado = entorno.ejecutor.execute_approved(request_id)

    assert resultado["status"] == "authorization_required"
    assert not (entorno.destino / "nuevo.txt").exists()


# ---------------------------------------------------------------
# Manipulación de argumentos tras autorizar
# ---------------------------------------------------------------

def test_cambiar_el_contenido_tras_autorizar_bloquea_la_ejecucion(entorno):
    request_id = _solicitar(entorno)
    _aprobar(entorno, request_id)

    entorno.ejecutor.pending_executions[request_id].arguments["content"] = "malicioso"

    with pytest.raises(ValueError, match="cambiado"):
        entorno.ejecutor.execute_approved(request_id)

    assert not (entorno.destino / "nuevo.txt").exists()


def test_cambiar_la_ruta_tras_autorizar_bloquea_la_ejecucion(entorno):
    request_id = _solicitar(entorno)
    _aprobar(entorno, request_id)

    otra = str(entorno.destino / "otro.txt")
    entorno.ejecutor.pending_executions[request_id].arguments["path"] = otra

    with pytest.raises(ValueError):
        entorno.ejecutor.execute_approved(request_id)

    assert not (entorno.destino / "otro.txt").exists()
    assert not (entorno.destino / "nuevo.txt").exists()


# ---------------------------------------------------------------
# Validación de entrada y límites
# ---------------------------------------------------------------

def test_argumento_desconocido_no_crea_solicitud(entorno):
    with pytest.raises(ValueError):
        entorno.ejecutor.execute(
            "create_file",
            {"path": entorno.ruta, "content": CONTENIDO, "extra": 1},
        )

    assert entorno.permisos.pending_requests == {}


def test_tipo_incorrecto_no_crea_solicitud(entorno):
    with pytest.raises(ValueError):
        entorno.ejecutor.execute(
            "create_file",
            {"path": entorno.ruta, "content": 123},
        )

    assert entorno.permisos.pending_requests == {}


def test_ruta_dentro_de_obsidian_rechazada_en_la_version_actual(entorno):
    # Comportamiento ACTUAL. El documento de estado indica que, en el diseño,
    # las escrituras dentro de la bóveda sí deberían pedir autorización.
    # Cuando se corrija, este test debe cambiar.
    ruta_en_vault = str(entorno.vault / "nota.md")

    with pytest.raises(ValueError):
        entorno.ejecutor.execute(
            "create_file",
            {"path": ruta_en_vault, "content": CONTENIDO},
        )


# ---------------------------------------------------------------
# Visibilidad de la aprobación
# ---------------------------------------------------------------

def test_la_solicitud_muestra_el_contenido_que_se_aprueba(entorno):
    resultado = entorno.ejecutor.execute(
        "create_file",
        {"path": entorno.ruta, "content": CONTENIDO},
    )

    assert resultado["request"]["details"]["arguments"]["content"] == CONTENIDO
    assert CONTENIDO in json.dumps(resultado["request"], ensure_ascii=False)


def test_el_archivo_contiene_exactamente_los_bytes_aprobados(entorno):
    contenido = "línea 1\r\nlínea 2\nñandú ✓"
    ruta = entorno.destino / "bytes.txt"

    resultado = entorno.ejecutor.execute(
        "create_file",
        {"path": str(ruta), "content": contenido},
    )
    request_id = resultado["request"]["id"]
    _aprobar(entorno, request_id)

    ejecucion = entorno.ejecutor.execute_approved(request_id)

    assert ejecucion["status"] == "success"
    assert ejecucion["result"]["verified"] is True
    assert ruta.read_bytes() == contenido.encode("utf-8")


def test_el_contexto_se_guarda_con_la_operacion_pendiente(entorno):
    resultado = entorno.ejecutor.execute(
        "create_file",
        {"path": entorno.ruta, "content": CONTENIDO},
        context="crea prueba.txt con hola",
    )
    request_id = resultado["request"]["id"]

    assert entorno.ejecutor.pending_executions[request_id].context == "crea prueba.txt con hola"
