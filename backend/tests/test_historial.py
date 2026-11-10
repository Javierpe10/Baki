"""El historial de chat vive en RAM, se envía solo como texto y se limita a N turnos."""

import json
from collections import deque

from app.claude_gateway import HISTORY_TURNS, ClaudeGateway


def _gateway(respuestas, enviados):
    gateway = ClaudeGateway.__new__(ClaudeGateway)
    gateway.history = deque(maxlen=HISTORY_TURNS)
    pendientes = list(respuestas)

    def falso_ask(prompt):
        enviados.append(prompt)
        return pendientes.pop(0)

    gateway.ask = falso_ask
    return gateway


def _mensaje(texto):
    return json.dumps({"type": "message", "content": texto})


def test_segundo_turno_incluye_el_primero():
    enviados = []
    gateway = _gateway([_mensaje("Hola, Javier"), _mensaje("Te llamas Javier")], enviados)

    gateway.plan("me llamo Javier")
    gateway.plan("¿cómo me llamo?")

    assert "Usuario: me llamo Javier" in enviados[1]
    assert "BAKI: Hola, Javier" in enviados[1]


def test_primer_turno_no_tiene_historial():
    enviados = []
    gateway = _gateway([_mensaje("hola")], enviados)

    gateway.plan("hola")

    assert "HISTORIAL RECIENTE" not in enviados[0]


def test_historial_se_limita_a_seis_turnos():
    enviados = []
    gateway = _gateway([_mensaje(f"r{i}") for i in range(8)], enviados)

    for i in range(8):
        gateway.plan(f"p{i}")

    # Antes de la octava petición, el historial contiene p1..p6.
    ultimo = enviados[-1]
    assert "Usuario: p0\n" not in ultimo
    assert "Usuario: p1\n" in ultimo
    assert "Usuario: p6\n" in ultimo
    assert len(gateway.history) == HISTORY_TURNS


def test_operacion_de_lectura_no_entra_en_el_historial():
    enviados = []
    gateway = _gateway(
        [json.dumps({"type": "read_file", "path": "C:\\datos\\a.txt"})],
        enviados,
    )

    plan = gateway.plan("lee C:\\datos\\a.txt")

    assert plan["type"] == "read_file"
    assert len(gateway.history) == 0
