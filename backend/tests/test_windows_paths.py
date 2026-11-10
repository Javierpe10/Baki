"""Pruebas de rutas en Windows: junctions, enlaces simbólicos y '..'.

Solo se ejecutan en Windows. En otros sistemas se saltan.
Ejecutar desde la carpeta backend:
    ..\\.venv\\Scripts\\python.exe -m pytest tests\\test_windows_paths.py -q -rs
"""

import os
import subprocess
from pathlib import Path

import pytest

from app.file_tools import FileTools
from app.permissions import PermissionManager
from app.tool_executor import ToolExecutor
from app.tool_registry import ToolRegistry


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Estas pruebas requieren Windows (junctions y reparse points).",
)


@pytest.fixture
def entorno(tmp_path):
    proyecto = tmp_path / "proyecto"
    proyecto.mkdir()
    vault = proyecto / "knowledge"
    vault.mkdir()
    fuera = tmp_path / "fuera"
    fuera.mkdir()

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

    return {
        "tmp": tmp_path,
        "proyecto": proyecto,
        "vault": vault,
        "fuera": fuera,
        "permisos": permisos,
        "ejecutor": ToolExecutor(registry=registro, permissions=permisos),
    }


def _crear_junction(enlace: Path, destino: Path):
    resultado = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(enlace), str(destino)],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        pytest.skip(f"No se pudo crear el junction: {resultado.stdout}{resultado.stderr}")


def _crear_symlink(enlace: Path, destino: Path):
    try:
        os.symlink(destino, enlace, target_is_directory=True)
    except OSError:
        pytest.skip("Sin privilegios para crear enlaces simbólicos.")


# ---------------------------------------------------------------
# Junctions y enlaces simbólicos
# ---------------------------------------------------------------

def test_junction_que_sale_del_proyecto_se_rechaza(entorno):
    enlace = entorno["proyecto"] / "atajo"
    _crear_junction(enlace, entorno["fuera"])

    with pytest.raises(ValueError):
        entorno["permisos"].request_resource_access(
            resource_type="file",
            resource_id=str(enlace / "nuevo.txt"),
            operation="create",
            reason="prueba",
        )

    assert entorno["permisos"].pending_requests == {}


def test_junction_hacia_la_boveda_se_rechaza(entorno):
    enlace = entorno["proyecto"] / "atajo_boveda"
    _crear_junction(enlace, entorno["vault"])

    with pytest.raises(ValueError):
        entorno["permisos"].request_resource_access(
            resource_type="file",
            resource_id=str(enlace / "nota.md"),
            operation="create",
            reason="prueba",
        )


def test_symlink_que_sale_del_proyecto_se_rechaza(entorno):
    enlace = entorno["proyecto"] / "enlace"
    _crear_symlink(enlace, entorno["fuera"])

    with pytest.raises(ValueError):
        entorno["permisos"].request_resource_access(
            resource_type="file",
            resource_id=str(enlace / "nuevo.txt"),
            operation="create",
            reason="prueba",
        )


def test_crear_archivo_a_traves_de_junction_no_crea_solicitud(entorno):
    enlace = entorno["proyecto"] / "atajo_ejecutor"
    _crear_junction(enlace, entorno["fuera"])

    with pytest.raises(ValueError):
        entorno["ejecutor"].execute(
            "create_file",
            {"path": str(enlace / "nuevo.txt"), "content": "x"},
        )

    assert entorno["permisos"].pending_requests == {}
    assert not (entorno["fuera"] / "nuevo.txt").exists()


# ---------------------------------------------------------------
# '..' y normalización
# ---------------------------------------------------------------

def test_punto_punto_no_permite_entrar_en_la_boveda(entorno):
    # fuera\..\proyecto\knowledge\nota.md resuelve dentro de la bóveda.
    entrada = str(entorno["fuera"] / ".." / "proyecto" / "knowledge" / "nota.md")

    with pytest.raises(ValueError):
        entorno["permisos"].request_resource_access(
            resource_type="file",
            resource_id=entrada,
            operation="create",
            reason="prueba",
        )


def test_punto_punto_se_normaliza_en_la_solicitud(entorno):
    entrada = str(entorno["proyecto"] / "sub" / ".." / "destino.txt")

    solicitud = entorno["permisos"].request_resource_access(
        resource_type="file",
        resource_id=entrada,
        operation="create",
        reason="prueba",
    )

    assert solicitud["resource"]["id"] == str(Path(entrada).resolve())
    assert ".." not in solicitud["resource"]["id"]
