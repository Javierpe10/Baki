
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.permissions import PermissionManager
from app.tool_registry import ToolRegistry


@dataclass
class PendingExecution:
    """Operación pendiente de autorización."""

    tool_name: str
    resource_type: str
    resource_id: str
    operation: str
    arguments: dict[str, Any]
    arguments_hash: str
    context: str | None = None


class ToolExecutor:
    """
    Ejecuta herramientas registradas únicamente después de validar
    los argumentos y obtener la autorización necesaria.

    Los handlers registrados deben ejecutar la operación concreta,
    sin solicitar ni consumir permisos por su cuenta.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionManager,
    ):
        self.registry = registry
        self.permissions = permissions
        self.pending_executions: dict[str, PendingExecution] = {}

    @staticmethod
    def _arguments_hash(arguments: dict[str, Any]) -> str:
        """Genera una huella estable de los argumentos."""

        try:
            serialized = json.dumps(
                arguments,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Los argumentos no se pueden serializar de forma segura."
            ) from exc

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: str | None = None,
    ) -> dict:

        # 1. Validar herramienta y argumentos.
        tool = self.registry.get(tool_name)
        validated_arguments = self.registry.validate_arguments(
            tool_name,
            arguments,
        )

        # 2. Identificar el recurso sobre el que se actuará.
        resource_id = validated_arguments[
            tool.resource_id_argument
        ]

        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError("El identificador del recurso no es válido.")

        resource_id = resource_id.strip()

        # 3. Crear una huella de los argumentos autorizables.
        arguments_hash = self._arguments_hash(validated_arguments)

        # 4. Solicitar autorización.
        request = self.permissions.request_resource_access(
            resource_type=tool.resource_type,
            resource_id=resource_id,
            operation=tool.operation,
            reason=f"BAKI necesita ejecutar la herramienta: {tool.name}",
            details={"arguments": dict(validated_arguments)},
        )

        if not isinstance(request, dict) or not request.get("id"):
            raise RuntimeError(
                "PermissionManager no devolvió una solicitud válida."
            )

        request_id = request["id"]

        # 5. Conservar exactamente la operación solicitada.
        self.pending_executions[request_id] = PendingExecution(
            tool_name=tool_name,
            resource_type=tool.resource_type,
            resource_id=resource_id,
            operation=tool.operation,
            arguments=validated_arguments.copy(),
            arguments_hash=arguments_hash,
            context=context,
        )

        return {
            "status": "authorization_required",
            "request": request,
            "tool": tool_name,
        }

    def execute_approved(self, request_id: str) -> dict:
        """Ejecuta una operación previamente autorizada."""

        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("Identificador de solicitud no válido.")

        pending = self.pending_executions.get(request_id)

        if pending is None:
            raise ValueError(
                "No existe una operación pendiente para esta solicitud."
            )

        # 1. Recuperar y volver a validar la herramienta.
        tool = self.registry.get(pending.tool_name)

        arguments = self.registry.validate_arguments(
            pending.tool_name,
            pending.arguments,
        )

        # 2. Comprobar que los argumentos no han cambiado.
        current_hash = self._arguments_hash(arguments)

        if current_hash != pending.arguments_hash:
            raise ValueError(
                "Los argumentos de la operación han cambiado."
            )

        # 3. Comprobar que la herramienta sigue apuntando al mismo recurso.
        if (
            tool.resource_type != pending.resource_type
            or tool.operation != pending.operation
            or arguments[tool.resource_id_argument] != pending.resource_id
        ):
            raise ValueError(
                "La operación ya no coincide con la autorización solicitada."
            )

        # 4. Consumir la autorización. Debe ser de un solo uso.
        authorized = self.permissions.consume_resource_approval(
            resource_type=pending.resource_type,
            resource_id=pending.resource_id,
            operation=pending.operation,
            request_id=request_id,
        )

        if not authorized:
            return {
                "status": "authorization_required",
                "message": "La autorización no está disponible o ha caducado.",
            }

        # 5. Eliminar la operación pendiente antes de ejecutar.
        self.pending_executions.pop(request_id, None)

        # 6. Ejecutar el handler.
        try:
            result = tool.handler(**arguments)
        except Exception:
            raise

        return {
            "status": "success",
            "tool": pending.tool_name,
            "result": result,
        }
