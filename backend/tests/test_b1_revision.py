import asyncio

import pytest

from app.config import ENV_FILE
from app.models import EstadoPago, EstadoPedido, Pedido
from app.ws import avisar_pedido
from tests.conftest import hacer_pedido, headers, id_de
from tests.test_ws import ws_panel


def estado(client, pid, nuevo, usuario):
    return client.patch(f"/api/panel/pedidos/{pid}/estado", json={"estado": nuevo}, headers=headers(usuario))


def pagar_mp(db, pid):
    # Simula que MP aprobó el pago (lo que hace aplicar_pago)
    p = db.get(Pedido, pid)
    p.estado_pago = EstadoPago.aprobado
    p.estado = EstadoPedido.recibido
    db.commit()


# ---------- 1. pendiente_pago no llega al panel ----------


def test_pedido_mp_sin_pagar_no_le_llega_al_panel(client, db, cantina, carta):
    with ws_panel(client, cantina) as ws:
        hacer_pedido(client, db, metodo_pago="mercadopago")  # este no tiene que llegar
        efectivo = hacer_pedido(client, db, metodo_pago="efectivo")
        msg = ws.receive_json()
    # Lo primero que llega es el de efectivo
    assert msg["pedido"]["numero"] == efectivo["numero"]


def test_pedido_mp_sin_pagar_si_le_llega_al_celu(client, db, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    with client.websocket_connect(f"/ws/pedido/{p['codigo']}") as ws:
        client.portal.call(avisar_pedido, id_de(db, p["codigo"]), "pedido_actualizado")
        msg = ws.receive_json()
    assert msg["pedido"]["estado"] == "pendiente_pago"


def test_cuando_mp_aprueba_al_panel_le_llega_pedido_nuevo(client, db, cantina, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    pid = id_de(db, p["codigo"])
    with ws_panel(client, cantina) as ws:
        pagar_mp(db, pid)
        client.portal.call(avisar_pedido, pid, "pedido_nuevo")
        msg = ws.receive_json()
    assert msg["evento"] == "pedido_nuevo"
    assert msg["pedido"]["estado"] == "recibido"


def test_cocina_no_ve_pendientes_de_pago_ni_con_todos(client, db, cocina, cantina, admin, carta):
    hacer_pedido(client, db, metodo_pago="mercadopago")
    hacer_pedido(client, db, metodo_pago="efectivo")

    def estados(usuario, query):
        r = client.get(f"/api/panel/pedidos{query}", headers=headers(usuario))
        return sorted(p["estado"] for p in r.json())

    assert estados(cocina, "?todos=true") == ["recibido"]
    assert estados(cocina, "?estado=pendiente_pago") == []
    assert estados(cantina, "?todos=true") == ["pendiente_pago", "recibido"]
    assert estados(admin, "?todos=true") == ["pendiente_pago", "recibido"]


# ---------- 2 y 3. requirements y .env ----------


def test_un_solo_requirements():
    raiz = ENV_FILE.parent.parent
    assert not (raiz / "requirements.txt").exists()
    assert (raiz / "backend" / "requirements.txt").exists()


def test_env_se_busca_en_backend():
    assert ENV_FILE.is_absolute()
    assert ENV_FILE.parent.name == "backend"
    assert ENV_FILE.name == ".env"


# ---------- 4. efectivo sin cobrar no se entrega ----------


@pytest.fixture
def listo(client, db, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    estado(client, pid, "en_preparacion", cantina)
    estado(client, pid, "listo", cantina)
    return pid


def test_efectivo_sin_cobrar_no_se_entrega(client, cantina, listo):
    r = estado(client, listo, "entregado", cantina)
    assert r.status_code == 400
    assert r.json()["detail"] == "Cobralo antes de marcarlo entregado"


def test_efectivo_cobrado_si_se_entrega(client, cantina, listo):
    client.post(f"/api/panel/pedidos/{listo}/cobrar", headers=headers(cantina))
    assert estado(client, listo, "entregado", cantina).status_code == 200


def test_cobrar_y_entregar(client, cantina, listo):
    r = client.post(f"/api/panel/pedidos/{listo}/cobrar-y-entregar", headers=headers(cantina))
    assert r.status_code == 200
    assert r.json()["estado"] == "entregado"
    assert r.json()["estado_pago"] == "aprobado"


def test_cobrar_y_entregar_si_ya_estaba_cobrado_solo_entrega(client, cantina, listo):
    client.post(f"/api/panel/pedidos/{listo}/cobrar", headers=headers(cantina))
    r = client.post(f"/api/panel/pedidos/{listo}/cobrar-y-entregar", headers=headers(cantina))
    assert r.status_code == 200 and r.json()["estado"] == "entregado"


def test_cobrar_y_entregar_pedido_que_no_esta_listo(client, db, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    r = client.post(f"/api/panel/pedidos/{pid}/cobrar-y-entregar", headers=headers(cantina))
    assert r.status_code == 400
    # No cobró nada si no pudo entregar
    db.expire_all()
    assert db.get(Pedido, pid).estado_pago == EstadoPago.pendiente


def test_cobrar_y_entregar_no_es_para_la_cocina(client, cocina, listo):
    r = client.post(f"/api/panel/pedidos/{listo}/cobrar-y-entregar", headers=headers(cocina))
    assert r.status_code == 403


def test_cobrar_y_entregar_avisa_por_ws(client, cantina, listo):
    with ws_panel(client, cantina) as ws:
        client.post(f"/api/panel/pedidos/{listo}/cobrar-y-entregar", headers=headers(cantina))
        msg = ws.receive_json()
    assert msg["evento"] == "pedido_actualizado"
    assert msg["pedido"]["estado"] == "entregado"


# ---------- 5. MP pagado: solo el admin cancela ----------


@pytest.fixture
def mp_pagado(client, db, carta):
    pid = id_de(db, hacer_pedido(client, db, metodo_pago="mercadopago")["codigo"])
    pagar_mp(db, pid)
    return pid


def test_cantina_no_cancela_mp_pagado(client, cantina, mp_pagado):
    r = estado(client, mp_pagado, "cancelado", cantina)
    assert r.status_code == 403
    assert "Solo el admin" in r.json()["detail"]


def test_admin_cancela_mp_pagado_con_aviso(client, admin, mp_pagado):
    r = estado(client, mp_pagado, "cancelado", admin)
    assert r.status_code == 200
    assert r.json()["estado"] == "cancelado"
    assert r.json()["aviso"] == "Acordate de devolver el pago desde Mercado Pago"


def test_cancelar_efectivo_sin_aviso(client, db, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db)["codigo"])
    r = estado(client, pid, "cancelado", cantina)
    assert r.status_code == 200
    assert r.json()["aviso"] is None


def test_cantina_si_cancela_mp_sin_pagar(client, db, cantina, carta):
    pid = id_de(db, hacer_pedido(client, db, metodo_pago="mercadopago")["codigo"])
    r = estado(client, pid, "cancelado", cantina)
    assert r.status_code == 200 and r.json()["aviso"] is None


def test_avisar_pedido_que_no_existe_no_rompe():
    asyncio.run(avisar_pedido(999, "pedido_actualizado"))
