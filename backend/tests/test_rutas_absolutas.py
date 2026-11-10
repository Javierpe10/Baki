"""Las rutas relativas se rechazan antes de crear ninguna solicitud de permiso."""

import pytest

from app.permissions import PermissionManager


@pytest.fixture
def permisos(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    return PermissionManager(
        str(vault),
        audit_path=str(tmp_path / "audit.jsonl"),
    )


@pytest.mark.parametrize("ruta", [
    "docs/BAKI_estado.md",
    "archivo.txt",
    "..\\docs\\archivo.txt",
])
def test_ruta_relativa_se_rechaza(permisos, ruta):
    with pytest.raises(ValueError, match="debe ser absoluta"):
        permisos._validated_path(ruta)


def test_ruta_absoluta_se_acepta(permisos, tmp_path):
    destino = tmp_path / "destino" / "archivo.txt"
    assert permisos._validated_path(str(destino)) == destino.resolve(strict=False)
