from pathlib import Path

from app.politica_herramientas import (
    DENEGAR,
    DENEGAR_PEDIR_APROBACION,
    PERMITIR,
    evaluar,
    huella,
    respuesta_hook,
)


def test_busqueda_web_no_requiere_aprobacion():
    assert evaluar("WebSearch", {"query": "x"}, []).accion == PERMITIR


def test_lectura_dentro_de_raiz_aprobada_permitida(tmp_path):
    raiz = tmp_path / "docs"
    raiz.mkdir()
    ruta = raiz / "nota.txt"
    d = evaluar("mcp__baki__read_file", {"path": str(ruta)}, [str(raiz)])
    assert d.accion == PERMITIR


def test_lectura_fuera_de_raiz_pide_aprobacion(tmp_path):
    raiz = tmp_path / "docs"
    raiz.mkdir()
    fuera = tmp_path / "otra" / "x.txt"
    d = evaluar("mcp__baki__read_file", {"path": str(fuera)}, [str(raiz)])
    assert d.accion == DENEGAR_PEDIR_APROBACION


def test_traversal_con_dos_puntos_no_escapa_de_la_raiz(tmp_path):
    raiz = tmp_path / "docs"
    raiz.mkdir()
    truco = str(raiz / ".." / "secreto.txt")
    d = evaluar("mcp__baki__read_file", {"path": truco}, [str(raiz)])
    assert d.accion == DENEGAR_PEDIR_APROBACION


def test_ruta_relativa_nunca_se_permite(tmp_path):
    d = evaluar("mcp__baki__read_file", {"path": "docs/a.txt"}, [str(tmp_path)])
    assert d.accion == DENEGAR_PEDIR_APROBACION


def test_ruta_ausente_o_no_texto_no_se_permite(tmp_path):
    assert evaluar("mcp__baki__list_dir", {}, [str(tmp_path)]).accion != PERMITIR
    assert evaluar("mcp__baki__list_dir", {"path": 5}, [str(tmp_path)]).accion != PERMITIR


def test_acciones_de_escritura_piden_aprobacion_aunque_la_ruta_este_aprobada(tmp_path):
    entrada = {"path": str(tmp_path / "a.txt"), "content": "x"}
    for nombre in ["mcp__baki__create_file", "mcp__baki__delete_file",
                   "mcp__baki__send_email", "mcp__baki__create_event"]:
        d = evaluar(nombre, entrada, [str(tmp_path)])
        assert d.accion == DENEGAR_PEDIR_APROBACION, nombre


def test_herramienta_desconocida_se_deniega():
    assert evaluar("mcp__otro__borrar_todo", {}, []).accion == DENEGAR


def test_entrada_no_objeto_se_deniega():
    assert evaluar("WebSearch", "texto", []).accion == DENEGAR


def test_huella_cambia_con_los_argumentos_y_es_estable():
    a = huella("mcp__baki__send_email", {"to": "a@x.com", "body": "hola"})
    b = huella("mcp__baki__send_email", {"body": "hola", "to": "a@x.com"})
    c = huella("mcp__baki__send_email", {"to": "b@x.com", "body": "hola"})
    assert a == b
    assert a != c


def test_respuesta_hook_permitir_devuelve_vacio():
    assert respuesta_hook(evaluar("WebSearch", {}, [])) == {}


def test_respuesta_hook_denegar_incluye_motivo():
    r = respuesta_hook(evaluar("mcp__baki__delete_file", {"path": "x"}, []))
    salida = r["hookSpecificOutput"]
    assert salida["hookEventName"] == "PreToolUse"
    assert salida["permissionDecision"] == "deny"
    assert salida["permissionDecisionReason"]
