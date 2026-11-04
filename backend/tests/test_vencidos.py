import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models import EstadoPedido, Pedido
from app.services import vencidos
from tests.conftest import hacer_pedido, id_de
from tests.test_ws import ws_panel


def envejecer(db, codigo, minutos):
    p = db.get(Pedido, id_de(db, codigo))
    p.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutos)
    db.commit()
    return p.id


def estado_de(db, pid):
    db.expire_all()
    return db.get(Pedido, pid).estado


@pytest.fixture
def viejo(client, db, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    return p["codigo"], envejecer(db, p["codigo"], 31)


def test_sin_token_no_hace_nada(db, viejo):
    _, pid = viejo
    assert vencidos.revisar_vencidos(db) == []
    assert estado_de(db, pid) == EstadoPedido.pendiente_pago


def test_sin_token_la_vuelta_no_tira_error(client, viejo):
    client.portal.call(vencidos.una_vuelta)


def test_cancela_los_vencidos(db, mp, viejo):
    _, pid = viejo
    assert vencidos.revisar_vencidos(db) == [(pid, "pedido_actualizado")]
    assert estado_de(db, pid) == EstadoPedido.cancelado
    assert mp.busquedas == 1  # le preguntó a MP antes de cancelar


def test_no_toca_los_recientes(client, db, mp, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    pid = envejecer(db, p["codigo"], 29)
    assert vencidos.revisar_vencidos(db) == []
    assert estado_de(db, pid) == EstadoPedido.pendiente_pago


def test_no_toca_los_de_efectivo(client, db, mp, carta):
    p = hacer_pedido(client, db, metodo_pago="efectivo")
    pid = envejecer(db, p["codigo"], 120)
    assert vencidos.revisar_vencidos(db) == []
    assert estado_de(db, pid) == EstadoPedido.recibido


def test_si_estaba_pagado_pasa_a_recibido(db, mp, viejo):
    codigo, pid = viejo
    mp.agregar_pago(777, codigo, 20000)
    assert vencidos.revisar_vencidos(db) == [(pid, "pedido_nuevo")]
    assert estado_de(db, pid) == EstadoPedido.recibido


def test_si_mp_no_responde_no_cancela(db, mp, viejo):
    _, pid = viejo
    mp.falla = True
    assert vencidos.revisar_vencidos(db) == []
    assert estado_de(db, pid) == EstadoPedido.pendiente_pago


def test_rechazado_y_vencido_se_cancela(db, mp, viejo):
    codigo, pid = viejo
    mp.agregar_pago(778, codigo, 20000, estado="rejected")
    vencidos.revisar_vencidos(db)
    assert estado_de(db, pid) == EstadoPedido.cancelado


def test_el_tiempo_sale_de_config(db, mp, viejo, monkeypatch):
    _, pid = viejo
    monkeypatch.setattr(settings, "minutos_para_pagar", 60)
    assert vencidos.revisar_vencidos(db) == []
    monkeypatch.setattr(settings, "minutos_para_pagar", 5)
    assert vencidos.revisar_vencidos(db) == [(pid, "pedido_actualizado")]


def test_la_vuelta_avisa_al_panel_si_estaba_pagado(client, db, mp, cantina, viejo):
    codigo, _ = viejo
    mp.agregar_pago(779, codigo, 20000)
    with ws_panel(client, cantina) as ws:
        client.portal.call(vencidos.una_vuelta)
        msg = ws.receive_json()
    assert msg["evento"] == "pedido_nuevo"
    assert msg["pedido"]["estado"] == "recibido"


def test_la_vuelta_avisa_al_celu_si_se_cancela(client, db, mp, viejo):
    codigo, _ = viejo
    with client.websocket_connect(f"/ws/pedido/{codigo}") as ws:
        client.portal.call(vencidos.una_vuelta)
        msg = ws.receive_json()
    assert msg["pedido"]["estado"] == "cancelado"


def test_la_tarea_arranca_con_la_app(client):
    tarea = client.app.state.tarea_vencidos
    assert not tarea.done()


def test_la_tarea_corre_sola(client, db, mp, viejo, monkeypatch):
    _, pid = viejo
    monkeypatch.setattr(settings, "segundos_entre_revisiones", 0.01)

    async def esperar():
        tarea = asyncio.create_task(vencidos.revisar_cada_tanto())
        for _ in range(200):
            await asyncio.sleep(0.01)
            if estado_de(db, pid) == EstadoPedido.cancelado:
                break
        tarea.cancel()

    client.portal.call(esperar)
    assert estado_de(db, pid) == EstadoPedido.cancelado
