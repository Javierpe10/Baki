"""Pruebas del agente BAKI: política, aprobaciones, rutas, SSRF, rutinas y WebSocket.

No llaman a Claude ni a servicios externos.
"""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.agente.herramientas  # noqa: F401
from app.agente import rutas
from app.agente.aprobaciones import GestorAprobaciones, huella
from app.agente.herramientas import archivos, rutinas, sistema, web
from app.agente.politica import (
    DENEGAR, PERMITIR, PREGUNTAR, crear_can_use_tool, crear_hook, evaluar,
)
from app.agente.registro import PREFIJO_MCP, REGISTRO


@pytest.fixture
def config(tmp_path):
    raiz = tmp_path / "aprobada"
    raiz.mkdir()
    return {"carpetas_aprobadas": [str(raiz)], "raiz": raiz}


def mcp(nombre):
    return PREFIJO_MCP + nombre


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------- política

def test_herramienta_desconocida_se_deniega(config):
    assert evaluar("Bash", {"command": "dir"}, config).accion == DENEGAR
    assert evaluar("Write", {}, config).accion == DENEGAR
    assert evaluar("mcp__otro__x", {}, config).accion == DENEGAR


def test_argumentos_no_dict_se_deniegan(config):
    assert evaluar(mcp("leer_archivo"), "x", config).accion == DENEGAR


def test_busqueda_web_es_nivel_1(config):
    assert evaluar("WebSearch", {"query": "x"}, config).accion == PERMITIR
    assert evaluar(mcp("leer_web"), {"url": "https://example.com"}, config).accion == PERMITIR


def test_lectura_dentro_de_aprobadas_es_nivel_1(config):
    ruta = str(config["raiz"] / "a.txt")
    assert evaluar(mcp("leer_archivo"), {"ruta": ruta}, config).accion == PERMITIR


def test_lectura_fuera_de_aprobadas_pide_aprobacion(config, tmp_path):
    ruta = str(tmp_path / "fuera.txt")
    assert evaluar(mcp("leer_archivo"), {"ruta": ruta}, config).accion == PREGUNTAR


def test_escape_con_puntos_pide_aprobacion(config):
    ruta = str(config["raiz"] / ".." / "fuera.txt")
    assert evaluar(mcp("leer_archivo"), {"ruta": ruta}, config).accion == PREGUNTAR


def test_ruta_relativa_pide_aprobacion(config):
    assert evaluar(mcp("leer_archivo"), {"ruta": "docs/a.txt"}, config).accion == PREGUNTAR


@pytest.mark.parametrize("nombre", [
    "crear_archivo", "escribir_archivo", "editar_archivo", "enviar_a_papelera", "ejecutar_powershell",
    "gmail_enviar", "gmail_papelera", "calendario_crear", "calendario_modificar", "calendario_borrar",
    "crm_crear_contactos", "crm_actualizar_contacto", "crm_enviar_mensaje", "redes_publicar",
    "guardar_memoria", "rutina_crear", "rutina_borrar",
])
def test_acciones_con_efecto_siempre_piden_aprobacion(nombre, config):
    entrada = {"ruta": str(config["raiz"] / "x.txt"), "contenido": "x"}
    assert evaluar(mcp(nombre), entrada, config).accion == PREGUNTAR


def test_todas_las_herramientas_tienen_nivel_valido(config):
    for nombre, h in REGISTRO.items():
        assert h.nivel_para({}, config) in (1, 2), nombre


def test_mover_dentro_de_aprobadas_es_nivel_1_y_fuera_nivel_2(config, tmp_path):
    dentro = {"origen": str(config["raiz"] / "a"), "destino": str(config["raiz"] / "b")}
    fuera = {"origen": str(config["raiz"] / "a"), "destino": str(tmp_path / "b")}
    assert evaluar(mcp("mover"), dentro, config).accion == PERMITIR
    assert evaluar(mcp("mover"), fuera, config).accion == PREGUNTAR


def test_crm_api_get_nivel_1_y_post_nivel_2(config):
    assert evaluar(mcp("crm_api"), {"metodo": "GET", "ruta": "/x"}, config).accion == PERMITIR
    assert evaluar(mcp("crm_api"), {"metodo": "POST", "ruta": "/x"}, config).accion == PREGUNTAR
    assert evaluar(mcp("crm_api"), {"metodo": "delete", "ruta": "/x"}, config).accion == PREGUNTAR


def test_abrir_url_y_app_conocida_nivel_1_ejecutable_nivel_2(config, tmp_path):
    assert evaluar(mcp("abrir"), {"objetivo": "https://google.com"}, config).accion == PERMITIR
    assert evaluar(mcp("abrir"), {"objetivo": "calculadora"}, config).accion == PERMITIR
    exe = tmp_path / "x.exe"
    exe.write_bytes(b"MZ")
    assert evaluar(mcp("abrir"), {"objetivo": str(exe)}, config).accion == PREGUNTAR
    assert evaluar(mcp("abrir"), {"objetivo": "programa_raro"}, config).accion == PREGUNTAR


def test_hook_traduce_la_decision(config):
    hook = crear_hook(lambda: config)
    salida = run(hook({"tool_name": "Bash", "tool_input": {}}, "id", None))
    assert salida["hookSpecificOutput"]["permissionDecision"] == "deny"
    salida = run(hook({"tool_name": "WebSearch", "tool_input": {"query": "x"}}, "id", None))
    assert salida["hookSpecificOutput"]["permissionDecision"] == "allow"
    salida = run(hook({"tool_name": mcp("gmail_enviar"), "tool_input": {}}, "id", None))
    assert salida["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_can_use_tool_espera_al_usuario_y_respeta_el_rechazo(config):
    llamadas = []

    async def aprobador(nombre, entrada):
        llamadas.append(nombre)
        return False, "rechazado"

    can_use = crear_can_use_tool(lambda: config, aprobador)
    r = run(can_use(mcp("gmail_enviar"), {"para": "a@b.com"}, None))
    assert r.behavior == "deny" and llamadas == [mcp("gmail_enviar")]
    r = run(can_use("Bash", {}, None))
    assert r.behavior == "deny" and len(llamadas) == 1  # denegado sin preguntar
    r = run(can_use("WebSearch", {"query": "x"}, None))
    assert r.behavior == "allow"


# ------------------------------------------------------------- aprobaciones

def test_aprobacion_se_resuelve_una_sola_vez(tmp_path):
    async def escenario():
        eventos = []

        async def notificar(e):
            eventos.append(e)

        g = GestorAprobaciones(tmp_path / "audit.jsonl", notificar=notificar)
        tarea = asyncio.create_task(g.solicitar(mcp("gmail_enviar"), {"para": "a@b.com"}))
        await asyncio.sleep(0.01)
        [pendiente] = g.publicas()
        assert pendiente["huella"] == huella(mcp("gmail_enviar"), {"para": "a@b.com"})
        assert g.resolver(pendiente["id"], True) is True
        assert g.resolver(pendiente["id"], True) is False
        aprobado, _ = await tarea
        return aprobado, eventos, g

    aprobado, eventos, g = run(escenario())
    assert aprobado is True
    assert [e["type"] for e in eventos] == ["aprobacion", "aprobacion_resuelta"]
    assert g.publicas() == []
    lineas = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert '"solicitada"' in lineas and '"aprobada"' in lineas


def test_aprobacion_caduca_como_rechazo(tmp_path):
    async def escenario():
        g = GestorAprobaciones(tmp_path / "audit.jsonl", espera_maxima=0.05)
        return await g.solicitar(mcp("crear_archivo"), {"ruta": "C:\\x"})

    aprobado, mensaje = run(escenario())
    assert aprobado is False and "caduc" in mensaje


def test_rechazar_todas(tmp_path):
    async def escenario():
        g = GestorAprobaciones(tmp_path / "audit.jsonl")
        t = asyncio.create_task(g.solicitar(mcp("gmail_enviar"), {}))
        await asyncio.sleep(0.01)
        g.rechazar_todas()
        return await t

    assert run(escenario())[0] is False


# ------------------------------------------------------------- rutas

def test_zonas_protegidas_no_se_escriben():
    backend_app = Path(__file__).resolve().parents[1] / "app" / "main.py"
    with pytest.raises(rutas.RutaNoValida):
        rutas.para_escritura(str(backend_app))
    with pytest.raises(rutas.RutaNoValida):
        rutas.para_escritura(str(Path.home() / ".ssh" / "id_rsa"))


def test_archivos_sensibles_nunca_son_nivel_1(config):
    env = str(config["raiz"] / ".env")
    assert evaluar(mcp("leer_archivo"), {"ruta": env}, config).accion == PREGUNTAR


def test_crear_editar_y_leer_archivo(config):
    ruta = str(config["raiz"] / "nota.txt")
    h = {n: REGISTRO[mcp(n)].sdk.handler for n in ("crear_archivo", "editar_archivo", "leer_archivo")}
    r = run(h["crear_archivo"]({"ruta": ruta, "contenido": "hola señor\nadiós"}))
    assert not r.get("is_error")
    r = run(h["crear_archivo"]({"ruta": ruta, "contenido": "otra"}))
    assert r.get("is_error")
    r = run(h["editar_archivo"]({"ruta": ruta, "buscar": "señor", "reemplazar": "BAKI"}))
    assert not r.get("is_error")
    assert Path(ruta).read_bytes() == "hola BAKI\nadiós".encode("utf-8")
    r = run(h["leer_archivo"]({"ruta": ruta}))
    assert "hola BAKI" in r["content"][0]["text"]


def test_editar_rechaza_fragmento_ambiguo(config):
    ruta = config["raiz"] / "d.txt"
    ruta.write_text("a a", encoding="utf-8")
    r = run(REGISTRO[mcp("editar_archivo")].sdk.handler({"ruta": str(ruta), "buscar": "a", "reemplazar": "b"}))
    assert r.get("is_error") and "2 veces" in r["content"][0]["text"]


# ------------------------------------------------------------- web

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8001/permissions/pending",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data",
    "http://192.168.1.1/",
    "http://10.0.0.1/",
    "file:///C:/Windows/win.ini",
    "http://user:pass@example.com/",
])
def test_ssrf_bloqueado(url):
    with pytest.raises(Exception):
        web.validar_url(url)


def test_extractor_html():
    ext = web._Extractor("https://x.com/a/")
    ext.feed("<html><title>T</title><script>malo()</script><p>Hola <a href='/c'>contacto</a></p></html>")
    assert "malo" not in "".join(ext.partes)
    assert ext.titulo == "T"
    assert ext.enlaces == [{"url": "https://x.com/c", "texto": "contacto"}]


# ------------------------------------------------------------- rutinas

def test_parsear_dias():
    assert rutinas.parsear_dias("laborables") == ["lun", "mar", "mie", "jue", "vie"]
    assert rutinas.parsear_dias("lun, vie") == ["lun", "vie"]
    with pytest.raises(Exception):
        rutinas.parsear_dias("lunes,funday")


def test_toca_ejecutar_una_vez_por_minuto():
    r = {"hora": "08:30", "dias": ["lun"], "activa": True}
    lunes = datetime(2026, 11, 9, 8, 30)
    assert rutinas.toca_ejecutar(r, lunes)
    r["ultima_ejecucion"] = "2026-11-09 08:30"
    assert not rutinas.toca_ejecutar(r, lunes)
    assert not rutinas.toca_ejecutar({"hora": "08:30", "dias": ["mar"]}, lunes)


# ------------------------------------------------------------- endpoints nuevos

def test_websocket_rechaza_origen_ajeno():
    from starlette.websockets import WebSocketDisconnect

    from app.main import app

    cliente = TestClient(app, base_url="http://127.0.0.1:8001")
    with pytest.raises(WebSocketDisconnect):
        with cliente.websocket_connect("/ws", headers={"origin": "http://evil.com"}) as ws:
            ws.receive_json()


def test_estado_y_tts_requieren_cabecera():
    from app.main import app

    cliente = TestClient(app, base_url="http://127.0.0.1:8001")
    assert cliente.get("/estado").status_code == 403
    assert cliente.post("/tts", json={"texto": "hola"}).status_code == 403
    assert cliente.post("/config", json={"modelo": "x"}, headers={"X-BAKI-Action": "1"}).status_code == 400


# ------------------------------------------------------------- skills, n8n y programador

from app.agente.config import DATA_DIR  # noqa: E402
from app.agente.herramientas import n8n as n8n_h  # noqa: E402
from app.agente.herramientas import programador as prog  # noqa: E402


def test_skill_es_nivel_1(config):
    assert evaluar("Skill", {"skill": "baki:grill-me"}, config).accion == PERMITIR


def test_configuracion_de_baki_protegida():
    with pytest.raises(rutas.RutaNoValida):
        rutas.para_escritura(str(DATA_DIR / "baki_config.json"))
    with pytest.raises(rutas.RutaNoValida):
        rutas.para_escritura(str(DATA_DIR / "plugin_baki" / "skills" / "x" / "SKILL.md"))


@pytest.mark.parametrize("nombre", [
    "n8n_crear_workflow", "n8n_actualizar_workflow", "n8n_activar", "n8n_borrar_workflow",
    "n8n_llamar_webhook", "programar_proyecto",
])
def test_n8n_y_programador_piden_aprobacion(nombre, config):
    assert evaluar(mcp(nombre), {}, config).accion == PREGUNTAR


def test_n8n_lecturas_nivel_1(config):
    for n in ("n8n_listar_workflows", "n8n_ver_workflow", "n8n_ejecuciones", "n8n_ver_ejecucion"):
        assert evaluar(mcp(n), {"id": "1"}, config).accion == PERMITIR


def test_n8n_valida_conexiones():
    nodos = [{"name": "Webhook", "type": "n8n-nodes-base.webhook"}, {"name": "Set", "type": "n8n-nodes-base.set"}]
    n8n_h._validar_nodos(nodos, {"Webhook": {"main": [[{"node": "Set", "type": "main", "index": 0}]]}})
    with pytest.raises(Exception):
        n8n_h._validar_nodos(nodos, {"Webhook": {"main": [[{"node": "NoExiste"}]]}})
    with pytest.raises(Exception):
        n8n_h._validar_nodos(nodos + [{"name": "Set", "type": "x"}], {})


def test_programador_solo_dentro_de_su_carpeta(tmp_path):
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    dentro = str(carpeta / "src" / "app.py")
    fuera = str(tmp_path / "otro.txt")
    assert prog.evaluar_programador("Write", {"file_path": dentro}, carpeta) == "allow"
    assert prog.evaluar_programador("Edit", {"file_path": dentro}, carpeta) == "allow"
    assert prog.evaluar_programador("Read", {"file_path": fuera}, carpeta) == "deny"
    assert prog.evaluar_programador("Write", {"file_path": str(carpeta / ".." / "x.py")}, carpeta) == "deny"
    assert prog.evaluar_programador("Write", {"file_path": str(carpeta / ".env")}, carpeta) == "deny"
    assert prog.evaluar_programador("Bash", {"command": "npm test"}, carpeta) == "ask"
    assert prog.evaluar_programador("Glob", {"pattern": "**/*.py"}, carpeta) == "allow"
    assert prog.evaluar_programador("WebSearch", {"query": "x"}, carpeta) == "allow"
    assert prog.evaluar_programador("Agent", {}, carpeta) == "deny"


def test_programador_rechaza_carpetas_raiz():
    with pytest.raises(Exception):
        prog.carpeta_valida(str(Path.home()))
    with pytest.raises(Exception):
        prog.carpeta_valida(str(Path.home() / "Desktop"))
    with pytest.raises(Exception):
        prog.carpeta_valida(str(DATA_DIR / "x"))


def test_aprobacion_por_grupo(tmp_path):
    async def escenario():
        g = GestorAprobaciones(tmp_path / "audit.jsonl")
        t1 = asyncio.create_task(g.solicitar("programador:Bash", {"command": "npm i"}, grupo="G"))
        t2 = asyncio.create_task(g.solicitar("programador:Bash", {"command": "npm test"}, grupo="G"))
        await asyncio.sleep(0.01)
        primera = g.publicas()[0]
        g.resolver(primera["id"], True, todo_el_grupo=True)
        r1, r2 = await t1, await t2
        r3 = await g.solicitar("programador:Bash", {"command": "ls"}, grupo="G")  # ya aprobado en bloque
        g.cerrar_grupo("G")
        t4 = asyncio.create_task(g.solicitar("programador:Bash", {"command": "ls"}, grupo="G"))
        await asyncio.sleep(0.01)
        g.rechazar_todas()
        return r1[0], r2[0], r3[0], (await t4)[0]

    assert run(escenario()) == (True, True, True, False)


def test_solo_una_ventana_habla():
    import app.main as m

    class WsFalso:
        def __init__(self):
            self.recibido = []

        async def send_json(self, datos):
            self.recibido.append(datos)

    a, b = WsFalso(), WsFalso()
    m.clientes_ws.clear()
    m.clientes_ws.update({a, b})
    m.cliente_voz = b
    run(m.difundir({"type": "delta", "texto": "hola"}))
    assert a.recibido[-1]["hablar"] is False and b.recibido[-1]["hablar"] is True
    # Si la ventana que hablaba se cierra, otra toma el relevo.
    m.clientes_ws.discard(b)
    run(m.difundir({"type": "delta", "texto": "x"}))
    assert a.recibido[-1]["hablar"] is True
    m.clientes_ws.clear()
    m.cliente_voz = None


def test_interfaz_sin_cache():
    from app.main import DIST, app

    if not (DIST / "index.html").is_file():
        pytest.skip("Interfaz sin compilar")
    r = TestClient(app, base_url="http://127.0.0.1:8001").get("/")
    assert "no-store" in r.headers.get("cache-control", "")


# ------------------------------------------------------------- paneles de la interfaz

def test_paneles_requieren_cabecera():
    from app.main import app

    c = TestClient(app, base_url="http://127.0.0.1:8001")
    for ruta in ("/skills", "/conversaciones", "/uso", "/tareas"):
        assert c.get(ruta).status_code == 403, ruta


def test_listar_skills_lee_las_del_plugin():
    from app.agente.panel import listar_skills

    skills = {s["nombre"]: s for s in listar_skills()}
    assert {"proyecto-nuevo", "grilling", "security-and-hardening"} <= set(skills)
    assert skills["grill-me"]["automatica"] is False
    assert skills["proyecto-nuevo"]["origen"] == "BAKI"


def test_conversacion_con_id_no_valido_se_rechaza():
    from app.main import app

    c = TestClient(app, base_url="http://127.0.0.1:8001")
    h = {"X-BAKI-Action": "1"}
    assert c.get("/conversaciones/../../etc", headers=h).status_code in (400, 404)
    assert c.get("/conversaciones/no-es-un-id", headers=h).status_code == 400
    assert c.post("/conversaciones/00000000-0000-0000-0000-000000000000/abrir", headers=h).status_code == 404


def test_consumo_hoy_suma_solo_hoy(tmp_path, monkeypatch):
    import json as _json
    from datetime import datetime as _dt, timedelta, timezone

    from app.agente import panel

    archivo = tmp_path / "consumo.jsonl"
    hoy = _dt.now(timezone.utc).isoformat()
    ayer = (_dt.now(timezone.utc) - timedelta(days=2)).isoformat()
    archivo.write_text("\n".join([
        _json.dumps({"timestamp": hoy, "uso": {"input_tokens": 10, "output_tokens": 5}}),
        _json.dumps({"timestamp": ayer, "uso": {"input_tokens": 999, "output_tokens": 999}}),
        "línea rota",
    ]), encoding="utf-8")
    monkeypatch.setattr(panel, "CONSUMO", archivo)
    assert panel.consumo_hoy() == {"turnos": 1, "tokens_procesados": 15, "tokens_generados": 5}


def test_renombrar_valida_entrada(monkeypatch):
    from app.agente import panel
    from app.main import app

    c = TestClient(app, base_url="http://127.0.0.1:8001")
    h = {"X-BAKI-Action": "1"}
    assert c.post("/conversaciones/x/renombrar", json={"titulo": "a"}).status_code == 403
    assert c.post("/conversaciones/no-id/renombrar", json={"titulo": "a"}, headers=h).status_code == 400
    uid = "00000000-0000-0000-0000-000000000000"
    assert c.post(f"/conversaciones/{uid}/renombrar", json={"titulo": "   "}, headers=h).status_code == 400
    assert c.post(f"/conversaciones/{uid}/renombrar", json={"titulo": "Nueva"}, headers=h).status_code == 404

    llamadas = []
    monkeypatch.setattr(panel, "listar_conversaciones", lambda limite=60: [{"id": uid}])
    import claude_agent_sdk
    monkeypatch.setattr(claude_agent_sdk, "rename_session", lambda sid, t, directory=None: llamadas.append((sid, t)))
    r = c.post(f"/conversaciones/{uid}/renombrar", json={"titulo": "  Clínica   Sonrisa  " + "x" * 200}, headers=h)
    assert r.status_code == 200
    assert llamadas[0][0] == uid and llamadas[0][1].startswith("Clínica Sonrisa") and len(llamadas[0][1]) == 90
