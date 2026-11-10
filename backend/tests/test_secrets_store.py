"""Pruebas del almacén de secretos con un backend en memoria."""

import json
from pathlib import Path

import pytest

from app.secrets_store import (
    SERVICIO,
    NOMBRE_INDICE,
    SecretStoreUnavailable,
    SecretsStore,
    validar_nombre,
)

APP_DIR = Path(__file__).resolve().parents[1] / "app"
MODULOS_CON_ACCESO = {"secrets_store.py", "secrets_cli.py"}


class MemoriaBackend:
    def __init__(self):
        self.datos = {}

    def set_password(self, servicio, usuario, valor):
        self.datos[(servicio, usuario)] = valor

    def get_password(self, servicio, usuario):
        return self.datos.get((servicio, usuario))

    def delete_password(self, servicio, usuario):
        del self.datos[(servicio, usuario)]


class BackendRoto:
    def _fallo(self, *args):
        raise OSError("sin backend")

    set_password = _fallo
    get_password = _fallo
    delete_password = _fallo


@pytest.fixture
def tienda():
    return SecretsStore(MemoriaBackend())


def test_guardar_y_leer_devuelven_el_mismo_valor(tienda):
    tienda.guardar("baki:google:refresh_token", "valor-secreto-123")
    assert tienda.leer("baki:google:refresh_token") == "valor-secreto-123"


def test_leer_inexistente_no_revela_otros_valores(tienda):
    tienda.guardar("baki:google:otro", "valor-secreto-456")
    with pytest.raises(KeyError) as error:
        tienda.leer("baki:google:inexistente")
    assert "valor-secreto-456" not in str(error.value)


def test_listar_muestra_nombres_y_no_valores(tienda):
    tienda.guardar("baki:google:oauth_client", "valor-secreto-789")
    assert tienda.listar() == ["baki:google:oauth_client"]
    assert "valor-secreto-789" not in json.dumps(tienda.listar())


def test_el_indice_no_contiene_valores(tienda):
    tienda.guardar("baki:google:oauth_client", "valor-secreto-000")
    indice = tienda._backend.datos[(SERVICIO, NOMBRE_INDICE)]
    assert "valor-secreto-000" not in indice


def test_borrar_quita_el_secreto_y_su_nombre(tienda):
    tienda.guardar("baki:google:refresh_token", "x-valor")
    tienda.borrar("baki:google:refresh_token")
    assert tienda.listar() == []
    with pytest.raises(KeyError):
        tienda.leer("baki:google:refresh_token")


def test_borrar_inexistente_falla(tienda):
    with pytest.raises(KeyError):
        tienda.borrar("baki:google:no_existe")


@pytest.mark.parametrize("nombre", [
    "google",
    "baki:google",
    "baki:google:",
    "baki:google:../x",
    "baki:_indice:nombres",
    "BAKI:google:x",
])
def test_nombres_no_validos_se_rechazan(nombre):
    with pytest.raises(ValueError):
        validar_nombre(nombre)


def test_valor_vacio_se_rechaza(tienda):
    with pytest.raises(ValueError):
        tienda.guardar("baki:google:x", "")


def test_sin_almacen_la_operacion_falla_cerrada():
    tienda = SecretsStore(BackendRoto())
    with pytest.raises(SecretStoreUnavailable):
        tienda.leer("baki:google:x")
    with pytest.raises(SecretStoreUnavailable):
        tienda.guardar("baki:google:x", "valor")


def test_ningun_modulo_lee_secretos_fuera_de_la_capa_permitida():
    infractores = [
        str(ruta.relative_to(APP_DIR))
        for ruta in APP_DIR.rglob("*.py")
        if ruta.name not in MODULOS_CON_ACCESO
        and "integraciones" not in ruta.relative_to(APP_DIR).parts
        and "secrets_store" in ruta.read_text(encoding="utf-8")
    ]
    assert infractores == []
