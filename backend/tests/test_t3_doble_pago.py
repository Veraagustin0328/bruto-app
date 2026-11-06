"""A2 (tarea 3): no dar otro link de MP si ya hay un pago aprobado o en proceso."""
import pytest

from app.models import EstadoPago, EstadoPedido, Pedido
from tests.conftest import hacer_pedido, id_de
from tests.test_ws import ws_panel


@pytest.fixture
def pedido_mp(client, db, carta):
    return hacer_pedido(client, db, metodo_pago="mercadopago")  # $20.000


def leer(db, codigo) -> Pedido:
    db.expire_all()
    return db.get(Pedido, id_de(db, codigo))


def link(client, codigo):
    return client.post(f"/api/pagos/{codigo}/preferencia")


# ---------- POST /preferencia ----------


def test_sin_pagos_da_el_link(client, mp, pedido_mp):
    assert link(client, pedido_mp["codigo"]).status_code == 200
    assert len(mp.preferencias_creadas) == 1


def test_con_un_pago_rechazado_da_otro_link(client, mp, pedido_mp):
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, "rejected")
    assert link(client, pedido_mp["codigo"]).status_code == 200


@pytest.mark.parametrize("estado", ["pending", "in_process", "authorized"])
def test_con_un_pago_en_proceso_no_da_otro_link(client, mp, pedido_mp, estado):
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, estado)
    r = link(client, pedido_mp["codigo"])
    assert r.status_code == 400
    assert "todavía está procesando" in r.json()["detail"]
    assert mp.preferencias_creadas == []


def test_rechazado_y_despues_otro_en_proceso(client, mp, pedido_mp):
    # Probó con una tarjeta (rechazada) y después con otra que quedó en proceso
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, "rejected")
    mp.agregar_pago(2, pedido_mp["codigo"], 20000, "in_process")
    assert link(client, pedido_mp["codigo"]).status_code == 400


def test_con_un_pago_aprobado_no_da_link_y_lo_aplica(client, db, mp, pedido_mp, cantina):
    # MP aprobó pero el aviso nunca llegó: en vez de cobrarle de nuevo, lo damos por pago
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, "approved")
    with ws_panel(client, cantina) as ws:
        r = link(client, pedido_mp["codigo"])
        msg = ws.receive_json()
    assert r.status_code == 400
    assert "ya está pago" in r.json()["detail"]
    assert mp.preferencias_creadas == []
    p = leer(db, pedido_mp["codigo"])
    assert p.estado == EstadoPedido.recibido
    assert p.estado_pago == EstadoPago.aprobado
    # A la cantina le suena como nuevo
    assert msg["evento"] == "pedido_nuevo"


def test_si_mp_no_contesta_no_da_link(client, mp, pedido_mp):
    # Sin saber si pagó, mejor no arriesgar un doble cobro
    mp.falla = True
    assert link(client, pedido_mp["codigo"]).status_code == 502
    assert mp.preferencias_creadas == []


# ---------- POST /verificar trae pago_mp ----------


def verificar(client, codigo):
    r = client.post(f"/api/pagos/{codigo}/verificar")
    assert r.status_code == 200, r.text
    return r.json()


def test_verificar_sin_pagos_dice_ninguno(client, mp, pedido_mp):
    v = verificar(client, pedido_mp["codigo"])
    assert v["pago_mp"] == "ninguno"
    assert v["estado"] == "pendiente_pago"


def test_verificar_en_proceso(client, mp, pedido_mp):
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, "in_process")
    v = verificar(client, pedido_mp["codigo"])
    assert v["pago_mp"] == "en_proceso"
    assert v["estado"] == "pendiente_pago"


def test_verificar_rechazado(client, mp, pedido_mp):
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, "rejected")
    v = verificar(client, pedido_mp["codigo"])
    assert v["pago_mp"] == "rechazado"
    assert v["estado_pago"] == "rechazado"


def test_verificar_aprobado(client, mp, pedido_mp):
    mp.agregar_pago(1, pedido_mp["codigo"], 20000, "rejected")
    mp.agregar_pago(2, pedido_mp["codigo"], 20000, "approved")
    v = verificar(client, pedido_mp["codigo"])
    assert v["pago_mp"] == "aprobado"
    assert v["estado"] == "recibido"
    # Sigue sin mandarle el teléfono al celu
    assert "telefono" not in v


def test_estado_en_mp():
    from app.services.pagos import estado_en_mp

    assert estado_en_mp([]) == "ninguno"
    assert estado_en_mp([{"status": "rejected"}, {"status": "cancelled"}]) == "rechazado"
    assert estado_en_mp([{"status": "rejected"}, {"status": "pending"}]) == "en_proceso"
    assert estado_en_mp([{"status": "in_process"}, {"status": "approved"}]) == "aprobado"
