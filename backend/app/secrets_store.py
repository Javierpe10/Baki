"""Almacén de secretos de BAKI.

Los valores viven en el Administrador de credenciales de Windows, a través
de keyring. Solo debe usarlo la capa de integración. Ningún valor se escribe
en archivos del proyecto, logs, auditoría ni prompts.
"""

import json
import re

SERVICIO = "BAKI"
PATRON_NOMBRE = re.compile(r"^baki:([a-z0-9_-]+):([a-z0-9_-]+)$")
SERVICIO_RESERVADO = "_indice"
NOMBRE_INDICE = "baki:_indice:nombres"


class SecretStoreUnavailable(RuntimeError):
    """No hay almacén de credenciales disponible. La integración no se ejecuta."""


def validar_nombre(nombre) -> None:
    if not isinstance(nombre, str):
        raise ValueError("Nombre de secreto no válido.")

    coincidencia = PATRON_NOMBRE.match(nombre)

    if not coincidencia or coincidencia.group(1) == SERVICIO_RESERVADO:
        raise ValueError(
            "Nombre de secreto no válido. Formato: baki:<servicio>:<nombre>."
        )


class SecretsStore:
    def __init__(self, backend):
        self._backend = backend

    def _llamar(self, funcion, *args):
        try:
            return funcion(*args)
        except Exception as error:
            raise SecretStoreUnavailable(
                "El almacén de credenciales ha fallado."
            ) from error

    def _indice(self) -> list[str]:
        crudo = self._llamar(self._backend.get_password, SERVICIO, NOMBRE_INDICE)
        return json.loads(crudo) if crudo else []

    def _guardar_indice(self, nombres: list[str]) -> None:
        self._llamar(
            self._backend.set_password,
            SERVICIO,
            NOMBRE_INDICE,
            json.dumps(sorted(set(nombres))),
        )

    def guardar(self, nombre: str, valor: str) -> None:
        validar_nombre(nombre)

        if not isinstance(valor, str) or not valor:
            raise ValueError("El valor del secreto no puede estar vacío.")

        self._llamar(self._backend.set_password, SERVICIO, nombre, valor)

        indice = self._indice()

        if nombre not in indice:
            indice.append(nombre)
            self._guardar_indice(indice)

    def leer(self, nombre: str) -> str:
        validar_nombre(nombre)

        valor = self._llamar(self._backend.get_password, SERVICIO, nombre)

        if valor is None:
            raise KeyError(f"No existe el secreto {nombre}.")

        return valor

    def borrar(self, nombre: str) -> None:
        validar_nombre(nombre)

        if self._llamar(self._backend.get_password, SERVICIO, nombre) is None:
            raise KeyError(f"No existe el secreto {nombre}.")

        self._llamar(self._backend.delete_password, SERVICIO, nombre)
        self._guardar_indice([n for n in self._indice() if n != nombre])

    def listar(self) -> list[str]:
        return self._indice()


def tienda_por_defecto() -> SecretsStore:
    try:
        import keyring
    except ImportError as error:
        raise SecretStoreUnavailable(
            "Falta la librería keyring. Instálala en el entorno virtual."
        ) from error

    return SecretsStore(keyring)
