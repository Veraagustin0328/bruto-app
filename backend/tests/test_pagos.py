import hashlib
import hmac

import pytest

from app.config import settings
from app.models import EstadoPago, EstadoPedido, Pedido
from tests.conftest import hacer_pedido, id_de
from tests.test_ws import ws_panel


@pytest.fixture
def pedido_mp(client, db, carta):
    # Animal doble + 2 extra carne = 20.000
    return hacer_pedido(client, db, metodo_pago="mercadopago")


def leer(db, codigo) -> Pedido:
    db.expire_all()
    return db.get(Pedido, id_de(db, codigo))


# ---------- preferencia ----------


def test_crear_preferencia(client, db, mp, pedido_mp):
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/preferencia")
    assert r.status_code == 200, r.text
    assert r.json()["preference_id"] == "pref-123"
    # Con token TEST- usa el link de sandbox
    assert "sandbox" in r.json()["link_pago"]
    assert leer(db, pedido_mp["codigo"]).mp_preference_id == "pref-123"

    datos = mp.preferencias_creadas[0]
    assert datos["external_reference"] == pedido_mp["codigo"]
    assert datos["items"][0]["unit_price"] == 20000
    assert datos["items"][0]["title"] == "Animal (Doble, 2x Extra carne y queso)"
    # En localhost no se manda webhook ni auto_return (MP los rechaza sin https)
    assert "notification_url" not in datos and "auto_return" not in datos


def test_preferencia_vence_a_los_minutos_de_config(client, db, mp, pedido_mp, monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(settings, "minutos_para_pagar", 10)
    client.post(f"/api/pagos/{pedido_mp['codigo']}/preferencia")
    vence = datetime.fromisoformat(mp.preferencias_creadas[0]["expiration_date_to"])
    minutos = (vence - datetime.now(timezone.utc)).total_seconds() / 60
    assert 9 < minutos <= 10


def test_preferencia_con_https_manda_webhook(client, db, mp, pedido_mp, monkeypatch):
    monkeypatch.setattr(settings, "backend_url", "https://api.bruto.com")
    monkeypatch.setattr(settings, "frontend_url", "https://bruto.com")
    client.post(f"/api/pagos/{pedido_mp['codigo']}/preferencia")
    datos = mp.preferencias_creadas[0]
    assert datos["notification_url"] == "https://api.bruto.com/api/pagos/webhook"
    assert datos["auto_return"] == "approved"


def test_preferencia_de_pedido_en_efectivo(client, db, mp, carta):
    p = hacer_pedido(client, db, metodo_pago="efectivo")
    r = client.post(f"/api/pagos/{p['codigo']}/preferencia")
    assert r.status_code == 400


def test_preferencia_de_pedido_que_no_existe(client, mp):
    assert client.post("/api/pagos/noexiste/preferencia").status_code == 400


def test_preferencia_cuando_mp_falla(client, mp, pedido_mp):
    mp.falla = True
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/preferencia")
    assert r.status_code == 502


def test_preferencia_sin_token(client, pedido_mp):
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/preferencia")
    assert r.status_code == 502


# ---------- verificar (el celu al volver de MP) ----------


def test_pago_aprobado(client, db, mp, cantina, pedido_mp):
    mp.agregar_pago(111, pedido_mp["codigo"], 20000)
    with ws_panel(client, cantina) as ws:
        r = client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
        msg = ws.receive_json()

    assert r.status_code == 200
    assert r.json()["estado"] == "recibido"
    assert r.json()["estado_pago"] == "aprobado"
    assert leer(db, pedido_mp["codigo"]).mp_payment_id == "111"
    # Le cae a la cantina como pedido nuevo, así suena
    assert msg["evento"] == "pedido_nuevo"


def test_pago_rechazado(client, db, mp, cantina, carta, pedido_mp):
    mp.agregar_pago(222, pedido_mp["codigo"], 20000, estado="rejected")
    with ws_panel(client, cantina) as ws:
        r = client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
        # El panel no tiene que enterarse: el que llega primero es este de efectivo
        efectivo = hacer_pedido(client, db, metodo_pago="efectivo")
        msg = ws.receive_json()

    assert r.json()["estado"] == "pendiente_pago"
    assert r.json()["estado_pago"] == "rechazado"
    assert msg["pedido"]["numero"] == efectivo["numero"]


def test_rechazado_y_despues_aprobado(client, db, mp, pedido_mp):
    mp.agregar_pago(222, pedido_mp["codigo"], 20000, estado="rejected")
    client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
    mp.agregar_pago(223, pedido_mp["codigo"], 20000)
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
    assert r.json()["estado"] == "recibido"


def test_monto_que_no_cierra(client, db, mp, pedido_mp):
    mp.agregar_pago(333, pedido_mp["codigo"], 100)
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
    assert r.json()["estado"] == "pendiente_pago"
    assert r.json()["estado_pago"] == "pendiente"


def test_verificar_sin_pagos(client, mp, pedido_mp):
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
    assert r.status_code == 200 and r.json()["estado"] == "pendiente_pago"


def test_verificar_pedido_que_no_existe(client, mp):
    assert client.post("/api/pagos/noexiste/verificar").status_code == 404


def test_verificar_cuando_mp_falla(client, mp, pedido_mp):
    mp.falla = True
    assert client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar").status_code == 502


# ---------- webhook ----------


def webhook(client, pago_id, headers=None):
    return client.post(
        f"/api/pagos/webhook?type=payment&data.id={pago_id}",
        json={"type": "payment", "data": {"id": pago_id}},
        headers=headers or {},
    )


def test_webhook_aprueba(client, db, mp, cantina, pedido_mp):
    mp.agregar_pago(444, pedido_mp["codigo"], 20000)
    with ws_panel(client, cantina) as ws:
        r = webhook(client, "444")
        msg = ws.receive_json()
    assert r.status_code == 200
    assert msg["evento"] == "pedido_nuevo"
    assert leer(db, pedido_mp["codigo"]).estado == EstadoPedido.recibido


def test_webhook_repetido_no_cambia_nada(client, db, mp, cantina, carta, pedido_mp):
    mp.agregar_pago(444, pedido_mp["codigo"], 20000)
    webhook(client, "444")
    with ws_panel(client, cantina) as ws:
        assert webhook(client, "444").status_code == 200
        # El segundo aviso no manda nada al panel
        efectivo = hacer_pedido(client, db, metodo_pago="efectivo")
        msg = ws.receive_json()
    assert msg["pedido"]["numero"] == efectivo["numero"]
    p = leer(db, pedido_mp["codigo"])
    assert p.estado == EstadoPedido.recibido and p.estado_pago == EstadoPago.aprobado


def test_webhook_de_otra_cosa_se_ignora(client, mp):
    r = client.post("/api/pagos/webhook", json={"type": "merchant_order", "data": {"id": "1"}})
    assert r.status_code == 200


def test_webhook_de_pago_que_mp_no_conoce(client, mp, pedido_mp):
    assert webhook(client, "999").status_code == 200


def test_webhook_sin_token_pide_reintento(client, pedido_mp):
    assert webhook(client, "444").status_code == 500


def firma(secreto, data_id, request_id, ts="1700000000"):
    manifiesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


def test_webhook_con_firma_valida(client, db, mp, pedido_mp, monkeypatch):
    monkeypatch.setattr(settings, "mp_webhook_secret", "secreto-mp")
    mp.agregar_pago(555, pedido_mp["codigo"], 20000)
    r = webhook(client, "555", headers=firma("secreto-mp", "555", "req-1"))
    assert r.status_code == 200
    assert leer(db, pedido_mp["codigo"]).estado == EstadoPedido.recibido


def test_webhook_con_firma_trucha(client, db, mp, pedido_mp, monkeypatch):
    monkeypatch.setattr(settings, "mp_webhook_secret", "secreto-mp")
    mp.agregar_pago(555, pedido_mp["codigo"], 20000)
    assert webhook(client, "555", headers=firma("otro-secreto", "555", "req-1")).status_code == 401
    assert webhook(client, "555").status_code == 401
    assert leer(db, pedido_mp["codigo"]).estado == EstadoPedido.pendiente_pago


def test_pago_de_un_pedido_cancelado_queda_cancelado(client, db, mp, admin, pedido_mp):
    p = leer(db, pedido_mp["codigo"])
    p.estado = EstadoPedido.cancelado
    db.commit()
    mp.agregar_pago(666, pedido_mp["codigo"], 20000)
    r = client.post(f"/api/pagos/{pedido_mp['codigo']}/verificar")
    assert r.json()["estado"] == "cancelado"
    assert r.json()["estado_pago"] == "aprobado"
