import pytest
from starlette.websockets import WebSocketDisconnect

from app.models import Rol
from app.security import crear_token
from tests.conftest import crear_usuario, hacer_pedido, headers, id_de


def ws_panel(client, usuario):
    return client.websocket_connect(f"/ws/panel?token={crear_token(usuario.id, usuario.rol.value)}")


def test_panel_sin_token_se_corta(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/panel") as ws:
            ws.receive_text()


def test_panel_con_usuario_dado_de_baja_se_corta(client, db):
    u = crear_usuario(db, Rol.cantina, activo=False)
    with pytest.raises(WebSocketDisconnect):
        with ws_panel(client, u) as ws:
            ws.receive_text()


def test_ping_pong(client, cantina):
    with ws_panel(client, cantina) as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_panel_recibe_pedido_nuevo(client, db, cocina, carta):
    with ws_panel(client, cocina) as ws:
        p = hacer_pedido(client, db)
        msg = ws.receive_json()
    assert msg["evento"] == "pedido_nuevo"
    assert msg["pedido"]["numero"] == p["numero"]
    assert msg["pedido"]["telefono"] == "2615550142"


def test_panel_recibe_cambios_de_estado(client, db, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    with ws_panel(client, cantina) as ws:
        client.patch(f"/api/panel/pedidos/{pid}/estado", json={"estado": "en_preparacion"}, headers=headers(cantina))
        msg = ws.receive_json()
    assert msg["evento"] == "pedido_actualizado"
    assert msg["pedido"]["estado"] == "en_preparacion"


def test_celu_recibe_su_pedido(client, db, cantina, carta):
    p = hacer_pedido(client, db)
    pid = id_de(db, p["codigo"])
    with client.websocket_connect(f"/ws/pedido/{p['codigo']}") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"
        client.patch(f"/api/panel/pedidos/{pid}/estado", json={"estado": "en_preparacion"}, headers=headers(cantina))
        msg = ws.receive_json()
    assert msg["evento"] == "pedido_actualizado"
    assert msg["pedido"]["estado"] == "en_preparacion"
    # Al celu no le mandamos el teléfono
    assert "telefono" not in msg["pedido"]


def test_celu_con_codigo_trucho_se_corta(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/pedido/noexiste") as ws:
            ws.receive_text()
