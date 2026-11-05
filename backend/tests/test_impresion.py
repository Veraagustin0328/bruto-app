from datetime import datetime, timedelta, timezone

import pytest
from starlette.websockets import WebSocketDisconnect

from app.models import EstadoPago, EstadoPedido, Pedido, Rol
from app.security import crear_token
from app.services.pedidos import inicio_jornada
from tests.conftest import crear_usuario, hacer_pedido, headers, id_de
from tests.test_ws import ws_panel


@pytest.fixture
def impresora(db):
    return crear_usuario(db, Rol.impresora)


def ws_impresion(client, usuario):
    return client.websocket_connect(f"/ws/impresion?token={crear_token(usuario.id, usuario.rol.value)}")


def pendientes(client, usuario):
    return client.get("/api/impresion/pendientes", headers=headers(usuario))


def test_pendientes_trae_lo_que_falta_imprimir(client, db, impresora, carta):
    a = id_de(db, hacer_pedido(client, db)["codigo"])
    b = id_de(db, hacer_pedido(client, db)["codigo"])
    c = id_de(db, hacer_pedido(client, db)["codigo"])
    hacer_pedido(client, db, metodo_pago="mercadopago", telefono="2615559999")  # sin pagar: no
    db.get(Pedido, b).impreso_at = datetime.now(timezone.utc)  # ya impreso: no
    db.get(Pedido, c).estado = EstadoPedido.en_preparacion  # en preparación: sí
    db.commit()

    r = pendientes(client, impresora)
    assert r.status_code == 200
    assert [p["id"] for p in r.json()] == [a, c]
    assert r.json()[0]["items"][0]["nombre_producto"] == "Animal"


def test_pendientes_no_trae_listos_ni_cancelados_ni_de_ayer(client, db, impresora, carta):
    a = id_de(db, hacer_pedido(client, db)["codigo"])
    b = id_de(db, hacer_pedido(client, db)["codigo"])
    c = id_de(db, hacer_pedido(client, db)["codigo"])
    db.get(Pedido, a).estado = EstadoPedido.listo
    db.get(Pedido, b).estado = EstadoPedido.cancelado
    db.get(Pedido, c).created_at = inicio_jornada() - timedelta(hours=1)
    db.commit()
    assert pendientes(client, impresora).json() == []


def test_marcar_impreso(client, db, impresora, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    r = client.post(f"/api/impresion/pedidos/{pid}/impreso", headers=headers(impresora))
    assert r.status_code == 200
    assert r.json()["impreso_at"] is not None
    assert pendientes(client, impresora).json() == []


def test_marcar_impreso_avisa_al_panel(client, db, impresora, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    with ws_panel(client, cantina) as ws:
        client.post(f"/api/impresion/pedidos/{pid}/impreso", headers=headers(impresora))
        msg = ws.receive_json()
    assert msg["pedido"]["impreso_at"] is not None


def test_marcar_impreso_que_no_existe(client, impresora, carta):
    assert client.post("/api/impresion/pedidos/999/impreso", headers=headers(impresora)).status_code == 404


def test_reimprimir_vuelve_a_pendientes(client, db, impresora, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    client.post(f"/api/impresion/pedidos/{pid}/impreso", headers=headers(impresora))
    client.post(f"/api/panel/pedidos/{pid}/reimprimir", headers=headers(cantina))
    assert [p["id"] for p in pendientes(client, impresora).json()] == [pid]


# ---------- permisos ----------


def test_admin_tambien_puede(client, admin, carta):
    assert pendientes(client, admin).status_code == 200


@pytest.mark.parametrize("rol", [Rol.cantina, Rol.cocina])
def test_cantina_y_cocina_no(client, db, carta, rol):
    u = crear_usuario(db, rol)
    assert pendientes(client, u).status_code == 403


def test_la_impresora_no_entra_al_panel(client, impresora, carta):
    h = headers(impresora)
    assert client.get("/api/panel/pedidos", headers=h).status_code == 403
    assert client.get("/api/carta", headers=h).status_code == 403
    assert client.get("/api/auth/usuarios", headers=h).status_code == 403


def test_la_impresora_no_entra_al_ws_del_panel(client, impresora):
    with pytest.raises(WebSocketDisconnect):
        with ws_panel(client, impresora) as ws:
            ws.receive_text()


def test_admin_crea_un_usuario_impresora(client, admin):
    nuevo = {"nombre": "Ticketera", "email": "ticketera@bruto.com", "password": "12345678", "rol": "impresora"}
    r = client.post("/api/auth/usuarios", json=nuevo, headers=headers(admin))
    assert r.status_code == 201 and r.json()["rol"] == "impresora"


# ---------- WebSocket del agente ----------


def test_ws_impresion_solo_impresora_y_admin(client, db, impresora, admin, cantina):
    with ws_impresion(client, impresora) as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"
    with ws_impresion(client, admin) as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"
    with pytest.raises(WebSocketDisconnect):
        with ws_impresion(client, cantina) as ws:
            ws.receive_text()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/impresion") as ws:
            ws.receive_text()


def test_reimprimir_le_llega_al_agente(client, db, impresora, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    with ws_impresion(client, impresora) as ws:
        client.post(f"/api/panel/pedidos/{pid}/reimprimir", headers=headers(cantina))
        msg = ws.receive_json()
    assert msg["evento"] == "imprimir"
    assert msg["pedido"]["id"] == pid


def test_pedido_nuevo_le_llega_al_agente(client, db, impresora, carta):
    with ws_impresion(client, impresora) as ws:
        p = hacer_pedido(client, db)
        msg = ws.receive_json()
    assert msg == {"evento": "imprimir", "pedido": msg["pedido"]}
    assert msg["pedido"]["numero"] == p["numero"]


def test_pedido_mp_le_llega_al_agente_recien_al_pagarse(client, db, impresora, mp, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    with ws_impresion(client, impresora) as ws:
        mp.agregar_pago(1, p["codigo"], 20000)
        client.post(f"/api/pagos/{p['codigo']}/verificar")
        msg = ws.receive_json()
    assert msg["evento"] == "imprimir"
    assert msg["pedido"]["estado_pago"] == EstadoPago.aprobado.value
