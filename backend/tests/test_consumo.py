"""El registro de consumo guarda tamaños y tokens, nunca el texto."""

import json

from app import claude_gateway
from app.claude_gateway import ClaudeGateway


def test_registrar_consumo_no_guarda_el_texto(tmp_path, monkeypatch):
    log = tmp_path / "usage_log.jsonl"
    monkeypatch.setattr(claude_gateway, "USAGE_LOG", log)
    gateway = ClaudeGateway.__new__(ClaudeGateway)

    gateway._registrar_consumo(
        "texto privado del usuario",
        {"usage": {"input_tokens": 10, "output_tokens": 3}, "total_cost_usd": 0.0},
    )

    contenido = log.read_text(encoding="utf-8")
    assert "texto privado" not in contenido
    entrada = json.loads(contenido)
    assert entrada["prompt_chars"] == len("texto privado del usuario")
    assert entrada["usage"] == {"input_tokens": 10, "output_tokens": 3}
