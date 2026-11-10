"""Lectura y listado de archivos con autorización previa."""

import json
from types import SimpleNamespace

import pytest

from app.file_tools import FileTools
from app.permissions import PermissionManager
from app.tool_executor import ToolExecutor
from app.tool_registry import ToolRegistry


@pytest.fixture
def entorno(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    carpeta = tmp_path / "datos"
    carpeta.mkdir()

    permisos = PermissionManager(str(vault), audit_path=str(tmp_path / "audit.jsonl"))
    file_tools = FileTools(permisos)

    registro = ToolRegistry()
    registro.register(
        name="read_file",
        description="Leer el contenido de un archivo de texto.",
        handler=file_tools._read_file_authorized,
        argument_types={"path": str},
        required_arguments={"path"},
        resource_type="file",
        operation="read",
        resource_id_argument="path",
    )
    registro.register(
        name="list_dir",
        description="Listar los nombres de una carpeta.",
        handler=file_tools._list_dir_authorized,
        argument_types={"path": str},
        required_arguments={"path"},
        resource_type="folder",
        operation="list",
        resource_id_argument="path",
    )

    return SimpleNamespace(
        vault=vault,
        carpeta=carpeta,
        permisos=permisos,
        ejecutor=ToolExecutor(registry=registro, permissions=permisos),
    )


def _aprobar_y_ejecutar(entorno, herramienta, ruta):
    resultado = entorno.ejecutor.execute(herramienta, {"path": str(ruta)})
    request_id = resultado["request"]["id"]
    entorno.permisos.approve(request_id)
    return entorno.ejecutor.execute_approved(request_id), request_id


# ---------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------

def test_leer_sin_aprobacion_no_devuelve_contenido(entorno):
    archivo = entorno.carpeta / "a.txt"
    archivo.write_text("secreto", encoding="utf-8")

    resultado = entorno.ejecutor.execute("read_file", {"path": str(archivo)})

    assert resultado["status"] == "authorization_required"
    assert "secreto" not in json.dumps(resultado, ensure_ascii=False)


def test_leer_aprobado_devuelve_contenido_exacto(entorno):
    archivo = entorno.carpeta / "a.txt"
    archivo.write_bytes("ñandú\n".encode("utf-8"))

    ejecucion, _ = _aprobar_y_ejecutar(entorno, "read_file", archivo)

    assert ejecucion["status"] == "success"
    assert ejecucion["result"]["content"] == "ñandú\n"


def test_leer_denegado_no_devuelve_contenido(entorno):
    archivo = entorno.carpeta / "a.txt"
    archivo.write_text("secreto", encoding="utf-8")

    resultado = entorno.ejecutor.execute("read_file", {"path": str(archivo)})
    entorno.permisos.deny(resultado["request"]["id"])
    ejecucion = entorno.ejecutor.execute_approved(resultado["request"]["id"])

    assert ejecucion["status"] == "authorization_required"
    assert "content" not in ejecucion


def test_archivo_demasiado_grande_se_rechaza(entorno, monkeypatch):
    monkeypatch.setattr(FileTools, "MAX_READ_BYTES", 10)
    archivo = entorno.carpeta / "grande.txt"
    archivo.write_text("x" * 11, encoding="utf-8")

    with pytest.raises(ValueError, match="límite"):
        _aprobar_y_ejecutar(entorno, "read_file", archivo)


def test_archivo_binario_no_se_lee(entorno):
    archivo = entorno.carpeta / "binario.bin"
    archivo.write_bytes(b"\xff\xfe\x00bin")

    with pytest.raises(ValueError, match="UTF-8"):
        _aprobar_y_ejecutar(entorno, "read_file", archivo)


def test_archivo_inexistente_falla(entorno):
    with pytest.raises(FileNotFoundError):
        _aprobar_y_ejecutar(entorno, "read_file", entorno.carpeta / "no.txt")


def test_aprobacion_de_lectura_no_sirve_para_crear(entorno):
    archivo = entorno.carpeta / "a.txt"
    archivo.write_text("x", encoding="utf-8")

    resultado = entorno.ejecutor.execute("read_file", {"path": str(archivo)})
    request_id = resultado["request"]["id"]
    entorno.permisos.approve(request_id)

    assert entorno.permisos.consume_resource_approval(
        resource_type="file",
        resource_id=str(archivo),
        operation="create",
        request_id=request_id,
    ) is False


def test_leer_dentro_de_la_boveda_se_rechaza(entorno):
    with pytest.raises(ValueError):
        entorno.ejecutor.execute(
            "read_file",
            {"path": str(entorno.vault / "nota.md")},
        )


# ---------------------------------------------------------------
# Listado
# ---------------------------------------------------------------

def test_listar_aprobado_devuelve_nombres_y_tipos_sin_contenido(entorno):
    (entorno.carpeta / "a.txt").write_text("secreto", encoding="utf-8")
    (entorno.carpeta / "sub").mkdir()

    ejecucion, _ = _aprobar_y_ejecutar(entorno, "list_dir", entorno.carpeta)

    nombres = {e["name"]: e["type"] for e in ejecucion["result"]["entries"]}
    assert nombres == {"a.txt": "file", "sub": "dir"}
    assert "secreto" not in json.dumps(ejecucion, ensure_ascii=False)


def test_listado_se_limita(entorno, monkeypatch):
    monkeypatch.setattr(FileTools, "MAX_LIST_ENTRIES", 2)
    for i in range(5):
        (entorno.carpeta / f"f{i}.txt").write_text("x", encoding="utf-8")

    ejecucion, _ = _aprobar_y_ejecutar(entorno, "list_dir", entorno.carpeta)

    assert len(ejecucion["result"]["entries"]) == 2
    assert ejecucion["result"]["truncated"] is True


def test_listar_un_archivo_falla(entorno):
    archivo = entorno.carpeta / "a.txt"
    archivo.write_text("x", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        _aprobar_y_ejecutar(entorno, "list_dir", archivo)
