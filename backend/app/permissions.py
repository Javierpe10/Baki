
import ctypes
import json
import os
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path


class PermissionManager:
    """
    Gestiona autorizaciones puntuales sobre recursos del sistema.

    No ejecuta operaciones.
    Cada autorización permite una única operación sobre un recurso concreto.
    """

    # Operaciones compatibles con FileTools.
    OPERATIONS = {
        "read",
        "list",
        "search",
        "create",
        "edit",
        "delete",
    }

    # Operaciones que podrá utilizar el sistema genérico de herramientas.
    RESOURCE_OPERATIONS = OPERATIONS | {
        "execute",
        "send",
        "post",
        "navigate",
        "download",
        "upload",
        "install",
        "configure",
        "purchase",
    }

    FILESYSTEM_RESOURCES = {"file", "folder"}

    REQUEST_TTL_SECONDS = 600
    APPROVAL_TTL_SECONDS = 120

    def __init__(self, vault_path: str, audit_path: str | None = None):
        self.vault_path = Path(vault_path).resolve(strict=True)

        if not self.vault_path.is_dir():
            raise ValueError("La ruta de Obsidian no es un directorio.")

        self.audit_path = (
            Path(audit_path).resolve()
            if audit_path
            else Path(__file__).with_name("permissions_audit.jsonl")
        )

        self.pending_requests = {}
        self.audit_log = []

        self._load_audit_log()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_path(path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Ruta no válida.")

        expanded = Path(os.path.expanduser(path))

        if not expanded.is_absolute():
            raise ValueError(
                "La ruta debe ser absoluta, por ejemplo "
                "C:\\Users\\...\\archivo.txt."
            )

        return Path(os.path.abspath(expanded))

    @staticmethod
    def _contains_reparse_point(path: Path) -> bool:
        """
        Detecta enlaces simbólicos y puntos de reanálisis de Windows,
        incluidas junctions, en los componentes existentes de la ruta.
        """

        current = Path(path.anchor)

        for part in path.parts[1:]:
            current = current / part

            if not os.path.lexists(current):
                continue

            if current.is_symlink():
                return True

            if os.name == "nt":
                attributes = ctypes.windll.kernel32.GetFileAttributesW(
                    str(current)
                )

                if attributes != -1 and attributes & 0x400:
                    return True

        return False

    def _validated_path(self, path: str) -> Path:
        target = self._normalize_path(path)

        if self._contains_reparse_point(target):
            raise ValueError(
                "No se permiten rutas que atraviesen enlaces "
                "simbólicos o puntos de reanálisis."
            )

        return target.resolve(strict=False)

    def is_trusted_vault_path(self, path: str) -> bool:
        target = self._validated_path(path)

        try:
            target.relative_to(self.vault_path)
            return True
        except ValueError:
            return False

    def _ensure_outside_vault(self, target: Path):
        try:
            target.relative_to(self.vault_path)
        except ValueError:
            return

        raise ValueError(
            "Obsidian está excluido de este sistema de permisos."
        )

    def _normalize_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> dict:
        """
        Normaliza un recurso y devuelve su representación canónica.
        Los recursos de archivos y carpetas utilizan rutas validadas.
        """

        if not isinstance(resource_type, str) or not resource_type.strip():
            raise ValueError("Tipo de recurso no válido.")

        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError("Identificador de recurso no válido.")

        resource_type = resource_type.strip().lower()

        if resource_type in self.FILESYSTEM_RESOURCES:
            target = self._validated_path(resource_id)
            self._ensure_outside_vault(target)
            resource_id = str(target)
        else:
            resource_id = resource_id.strip()

        return {
            "type": resource_type,
            "id": resource_id,
        }

    def _write_audit(self, event: dict):
        """
        Persiste cada evento.
        Si no puede registrarlo, falla de forma segura.
        """

        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        with self.audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())

        self.audit_log.append(event)

    def _load_audit_log(self):
        if not self.audit_path.exists():
            return

        with self.audit_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    self.audit_log.append(json.loads(line))

    def _log(self, request: dict, event: str):
        resource = request.get("resource", {})

        self._write_audit({
            "request_id": request["id"],
            "resource": resource,
            "path": request.get("path"),
            "operation": request["operation"],
            "reason": request["reason"],
            "event": event,
            "timestamp": self._timestamp(),
        })

    def _create_request(
        self,
        resource: dict,
        operation: str,
        reason: str,
        details: dict | None = None,
    ) -> dict:
        request = {
            "id": str(uuid.uuid4()),
            "resource": resource,
            "operation": operation,
            "reason": reason.strip(),
            "details": dict(details or {}),
            "status": "pending",
            "created_at": self._timestamp(),
            "expires_at": (
                self._now()
                + timedelta(seconds=self.REQUEST_TTL_SECONDS)
            ).isoformat(),
        }

        # Compatibilidad con el frontend y FileTools actuales.
        if resource["type"] in self.FILESYSTEM_RESOURCES:
            request["path"] = resource["id"]

        self.pending_requests[request["id"]] = request

        return request.copy()

    # ---------------------------------------------------------
    # API GENÉRICA DE RECURSOS
    # ---------------------------------------------------------

    def request_resource_access(
        self,
        resource_type: str,
        resource_id: str,
        operation: str,
        reason: str,
        details: dict | None = None,
    ) -> dict:

        if operation not in self.RESOURCE_OPERATIONS:
            raise ValueError("Operación no permitida.")

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Debes indicar el motivo del acceso.")

        resource = self._normalize_resource(
            resource_type,
            resource_id,
        )

        return self._create_request(
            resource=resource,
            operation=operation,
            reason=reason,
            details=details,
        )

    # ---------------------------------------------------------
    # APROBACIÓN Y RECHAZO
    # ---------------------------------------------------------

    def approve(self, request_id: str) -> dict:
        request = self.pending_requests.get(request_id)

        if not request or request["status"] != "pending":
            raise ValueError("Solicitud inexistente o no disponible.")

        if self._now() >= datetime.fromisoformat(request["expires_at"]):
            request["status"] = "expired"
            self._log(request, "expired")
            raise ValueError("La solicitud ha caducado.")

        request["status"] = "approved"
        request["approved_at"] = self._timestamp()
        request["approval_expires_at"] = (
            self._now()
            + timedelta(seconds=self.APPROVAL_TTL_SECONDS)
        ).isoformat()

        self._log(request, "approved")

        return request.copy()

    def deny(self, request_id: str) -> dict:
        request = self.pending_requests.get(request_id)

        if not request or request["status"] != "pending":
            raise ValueError("Solicitud inexistente o no disponible.")

        request["status"] = "denied"
        self._log(request, "denied")

        return request.copy()

    # ---------------------------------------------------------
    # CONSUMO DE AUTORIZACIONES
    # ---------------------------------------------------------

    def consume_resource_approval(
        self,
        resource_type: str,
        resource_id: str,
        operation: str,
        request_id: str | None = None,
    ) -> bool:
        """
        Comprueba y consume una autorización genérica.
        Una autorización solo puede consumirse una vez.
        """

        if operation not in self.RESOURCE_OPERATIONS:
            return False

        try:
            resource = self._normalize_resource(
                resource_type,
                resource_id,
            )
        except (ValueError, OSError):
            return False

        now = self._now()

        for request in self.pending_requests.values():

            if request_id is not None and request["id"] != request_id:
                continue

            if (
                request["status"] != "approved"
                or request.get("resource") != resource
                or request["operation"] != operation
            ):
                continue

            if now >= datetime.fromisoformat(
                request["approval_expires_at"]
            ):
                request["status"] = "expired"
                self._log(request, "expired")
                return False

            # Registrar antes de consumir.
            # Si falla la auditoría, la autorización no se consume.
            self._log(request, "consumed")

            request["status"] = "consumed"

            return True

        return False
