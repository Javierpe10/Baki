"""Pruebas de la cabecera obligatoria en los endpoints de permisos y chat.

Solo se prueban respuestas que no tocan operaciones reales ni llaman a Claude.
"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app, base_url="http://127.0.0.1:8001")
CABECERA = {"X-BAKI-Action": "1"}


def test_health_no_requiere_cabecera():
    assert client.get("/health").status_code == 200


def test_pendientes_sin_cabecera_devuelve_403():
    assert client.get("/permissions/pending").status_code == 403


def test_pendientes_con_cabecera_devuelve_200():
    assert client.get("/permissions/pending", headers=CABECERA).status_code == 200


def test_aprobar_sin_cabecera_devuelve_403():
    assert client.post("/permissions/no-existe/approve").status_code == 403


def test_denegar_sin_cabecera_devuelve_403():
    assert client.post("/permissions/no-existe/deny").status_code == 403


def test_aprobar_con_cabecera_y_id_inexistente_devuelve_400():
    respuesta = client.post("/permissions/no-existe/approve", headers=CABECERA)
    assert respuesta.status_code == 400


def test_chat_sin_cabecera_devuelve_403():
    respuesta = client.post("/chat", json={"message": "hola"})
    assert respuesta.status_code == 403


def test_pendientes_incluyen_el_contenido_que_se_aprueba(tmp_path):
    from app.main import permissions, tool_executor

    resultado = tool_executor.execute(
        "create_file",
        {"path": str(tmp_path / "visible.txt"), "content": "contenido visible"},
    )
    request_id = resultado["request"]["id"]

    try:
        respuesta = client.get("/permissions/pending", headers=CABECERA)
        items = [item for item in respuesta.json() if item["id"] == request_id]

        assert respuesta.status_code == 200
        assert len(items) == 1
        assert items[0]["details"]["arguments"]["content"] == "contenido visible"
    finally:
        tool_executor.pending_executions.pop(request_id, None)
        permissions.pending_requests.pop(request_id, None)


def test_ruta_antigua_de_creacion_ya_no_existe():
    respuesta = client.post(
        "/tools/files/create",
        json={"path": "x.txt", "content": "x"},
        headers=CABECERA,
    )
    assert respuesta.status_code in (404, 405)


def test_ruta_antigua_de_solicitud_ya_no_existe():
    respuesta = client.post(
        "/permissions/request",
        json={"path": "x.txt", "operation": "create", "reason": "x"},
        headers=CABECERA,
    )
    assert respuesta.status_code in (404, 405)


def test_denegar_elimina_la_operacion_pendiente(tmp_path):
    from app.main import permissions, tool_executor

    resultado = tool_executor.execute(
        "create_file",
        {"path": str(tmp_path / "denegado.txt"), "content": "no"},
    )
    request_id = resultado["request"]["id"]

    try:
        respuesta = client.post(f"/permissions/{request_id}/deny", headers=CABECERA)

        assert respuesta.status_code == 200
        assert request_id not in tool_executor.pending_executions
        assert not (tmp_path / "denegado.txt").exists()
    finally:
        tool_executor.pending_executions.pop(request_id, None)
        permissions.pending_requests.pop(request_id, None)


def test_ejecutar_sin_operacion_pendiente_devuelve_400():
    respuesta = client.post(
        "/tools/files/execute/no-existe",
        headers=CABECERA,
    )
    assert respuesta.status_code == 400


def test_host_ajeno_devuelve_403_aunque_la_cabecera_sea_correcta():
    # DNS rebinding: la página maliciosa llega con su propio Host.
    respuesta = client.get(
        "/permissions/pending",
        headers={**CABECERA, "Host": "evil.com:8001"},
    )
    assert respuesta.status_code == 403


def test_host_localhost_con_cabecera_devuelve_200():
    respuesta = client.get(
        "/permissions/pending",
        headers={**CABECERA, "Host": "localhost:8001"},
    )
    assert respuesta.status_code == 200


def test_origin_ajeno_devuelve_403():
    respuesta = client.get(
        "/permissions/pending",
        headers={**CABECERA, "Origin": "http://evil.com"},
    )
    assert respuesta.status_code == 403


def test_origin_del_frontend_devuelve_200():
    respuesta = client.get(
        "/permissions/pending",
        headers={**CABECERA, "Origin": "http://localhost:5173"},
    )
    assert respuesta.status_code == 200
