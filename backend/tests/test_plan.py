"""El plan de Claude solo puede proponer herramientas conocidas."""

from collections import deque

from app.claude_gateway import HISTORY_TURNS, ClaudeGateway


def _plan(respuesta_de_claude):
    gateway = ClaudeGateway.__new__(ClaudeGateway)
    gateway.history = deque(maxlen=HISTORY_TURNS)
    gateway.ask = lambda prompt: respuesta_de_claude
    return gateway.plan("petición de prueba")


def test_plan_acepta_read_file():
    plan = _plan('{"type": "read_file", "path": "C:\\\\datos\\\\a.txt"}')
    assert plan == {"type": "read_file", "path": "C:\\datos\\a.txt"}


def test_plan_acepta_list_dir():
    plan = _plan('{"type": "list_dir", "path": "C:\\\\datos"}')
    assert plan == {"type": "list_dir", "path": "C:\\datos"}


def test_plan_rechaza_herramientas_desconocidas():
    plan = _plan('{"type": "delete_file", "path": "C:\\\\x.txt"}')
    assert plan["type"] == "message"


def test_plan_create_file_sin_contenido_no_se_acepta():
    plan = _plan('{"type": "create_file", "path": "C:\\\\x.txt"}')
    assert plan["type"] == "message"
