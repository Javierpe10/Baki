
from pathlib import Path

from app.permissions import PermissionManager


class FileTools:
    """Operaciones de archivos. Solo se ejecutan desde ToolExecutor, tras autorización."""

    # Límites de lectura: evitan enviar a Claude archivos enormes.
    MAX_READ_BYTES = 40_000
    MAX_LIST_ENTRIES = 200

    def __init__(self, permissions: PermissionManager):
        self.permissions = permissions

    def _create_file_authorized(self, path: str, content: str) -> dict:
        """
        Ejecuta la creación de un archivo.

        La autorización debe haber sido validada previamente
        por ToolExecutor.
        """

        target = self.permissions._validated_path(path)

        if target.exists():
            raise FileExistsError("El archivo ya existe.")

        if not target.parent.is_dir():
            raise FileNotFoundError(
                "La carpeta de destino no existe."
            )

        data = content.encode("utf-8")

        # Escritura binaria: los bytes en disco son exactamente los aprobados.
        with target.open("xb") as file:
            file.write(data)

        # Verificación real: leer el archivo y comparar con lo aprobado.
        if not target.is_file() or target.read_bytes() != data:
            try:
                target.unlink()
            except OSError:
                pass

            raise RuntimeError(
                "La verificación ha fallado: el contenido escrito "
                "no coincide con el contenido aprobado."
            )

        return {
            "status": "success",
            "path": str(target),
            "bytes": len(data),
            "verified": True,
        }

    def _read_file_authorized(self, path: str) -> dict:
        """Lee un archivo de texto. Requiere autorización previa de tipo 'read'."""

        target = self.permissions._validated_path(path)

        if not target.is_file():
            raise FileNotFoundError(
                "El archivo no existe o no es un archivo regular."
            )

        size = target.stat().st_size

        if size > self.MAX_READ_BYTES:
            raise ValueError(
                f"El archivo supera el límite de lectura "
                f"({self.MAX_READ_BYTES} bytes)."
            )

        data = target.read_bytes()

        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "El archivo no es texto UTF-8 y no se puede leer."
            ) from exc

        return {
            "status": "success",
            "path": str(target),
            "bytes": len(data),
            "content": content,
        }

    def _list_dir_authorized(self, path: str) -> dict:
        """Lista nombres y tipos de una carpeta. No lee contenidos."""

        target = self.permissions._validated_path(path)

        if not target.is_dir():
            raise FileNotFoundError(
                "La carpeta no existe o la ruta no es una carpeta."
            )

        todas = sorted(target.iterdir(), key=lambda e: e.name.lower())

        entries = [
            {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
            }
            for entry in todas[: self.MAX_LIST_ENTRIES]
        ]

        return {
            "status": "success",
            "path": str(target),
            "entries": entries,
            "truncated": len(todas) > self.MAX_LIST_ENTRIES,
        }
