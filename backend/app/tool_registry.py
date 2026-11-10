
import re

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """Definición y configuración de una herramienta de BAKI."""

    name: str
    description: str
    handler: Callable

    argument_types: dict[str, type]
    required_arguments: set[str]

    resource_type: str
    operation: str
    resource_id_argument: str


class ToolRegistry:
    """
    Registro central de herramientas.

    Se encarga de:
    - Registrar herramientas disponibles.
    - Evitar nombres duplicados.
    - Describir sus argumentos.
    - Validar los argumentos recibidos.
    - Proporcionar información para el motor de razonamiento.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable,
        argument_types: dict[str, type],
        required_arguments: set[str],
        resource_type: str,
        operation: str,
        resource_id_argument: str,
    ) -> None:

        if not isinstance(name, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", name
        ):
            raise ValueError("Nombre de herramienta no válido.")

        if name in self._tools:
            raise ValueError(f"La herramienta '{name}' ya está registrada.")

        if not isinstance(description, str) or not description.strip():
            raise ValueError("La descripción es obligatoria.")

        if not callable(handler):
            raise ValueError("El ejecutor de la herramienta no es válido.")

        if not isinstance(argument_types, dict) or not argument_types:
            raise ValueError("Debes definir los argumentos de la herramienta.")

        if not all(
            isinstance(arg, str)
            and arg
            and isinstance(arg_type, type)
            for arg, arg_type in argument_types.items()
        ):
            raise ValueError("Definición de argumentos no válida.")

        if not isinstance(required_arguments, set):
            raise ValueError("Los argumentos obligatorios deben ser un set.")

        if not required_arguments.issubset(argument_types):
            raise ValueError(
                "Hay argumentos obligatorios que no están definidos."
            )

        if resource_id_argument not in argument_types:
            raise ValueError(
                "El identificador del recurso debe ser un argumento definido."
            )

        if not isinstance(resource_type, str) or not resource_type.strip():
            raise ValueError("Tipo de recurso no válido.")

        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("Operación no válida.")

        self._tools[name] = ToolDefinition(
            name=name,
            description=description.strip(),
            handler=handler,
            argument_types=argument_types.copy(),
            required_arguments=required_arguments.copy(),
            resource_type=resource_type.strip().lower(),
            operation=operation.strip().lower(),
            resource_id_argument=resource_id_argument,
        )

    def get(self, name: str) -> ToolDefinition:
        """Recupera una herramienta registrada."""

        tool = self._tools.get(name)

        if tool is None:
            raise ValueError(f"Herramienta desconocida: {name}")

        return tool

    def exists(self, name: str) -> bool:
        """Comprueba si una herramienta está registrada."""

        return name in self._tools

    def list_tools(self) -> list[dict]:
        """Devuelve las herramientas disponibles y sus metadatos."""

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "resource_type": tool.resource_type,
                "operation": tool.operation,
                "resource_id_argument": tool.resource_id_argument,
                "required_arguments": sorted(tool.required_arguments),
                "arguments": {
                    name: argument_type.__name__
                    for name, argument_type in tool.argument_types.items()
                },
            }
            for tool in self._tools.values()
        ]

    def validate_arguments(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict:
        """Valida los argumentos antes de ejecutar una herramienta."""

        tool = self.get(name)

        if not isinstance(arguments, dict):
            raise ValueError("Los argumentos deben ser un objeto.")

        unknown_arguments = set(arguments) - set(tool.argument_types)

        if unknown_arguments:
            raise ValueError(
                "Argumentos desconocidos: "
                + ", ".join(sorted(unknown_arguments))
            )

        missing_arguments = tool.required_arguments - set(arguments)

        if missing_arguments:
            raise ValueError(
                "Faltan argumentos obligatorios: "
                + ", ".join(sorted(missing_arguments))
            )

        validated = {}

        for argument_name, value in arguments.items():
            expected_type = tool.argument_types[argument_name]

            # Evita aceptar True o False como números enteros.
            if expected_type in (int, float, bool):
                valid = type(value) is expected_type
            else:
                valid = isinstance(value, expected_type)

            if not valid:
                raise ValueError(
                    f"Tipo incorrecto para '{argument_name}'. "
                    f"Se esperaba {expected_type.__name__}."
                )

            validated[argument_name] = value

        return validated

    def get_tool_schemas(self) -> list[dict]:
        """
        Devuelve definiciones de herramientas en formato
        compatible con esquemas JSON.
        """

        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }

        schemas = []

        for tool in self._tools.values():
            properties = {}

            for name, argument_type in tool.argument_types.items():
                json_type = type_mapping.get(argument_type)

                if json_type is None:
                    raise ValueError(
                        f"Tipo no compatible en '{tool.name}': {name}"
                    )

                properties[name] = {"type": json_type}

            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": sorted(tool.required_arguments),
                    "additionalProperties": False,
                },
            })

        return schemas
