from datetime import datetime, timezone

import pytest

from app.models import EstadoPedido, Pedido
from tests.conftest import hacer_pedido, headers, id_de


@pytest.fixture
def pedido(client, db, carta):
    p = hacer_pedido(client, db)
    return id_de(db, p["codigo"])


def estado(client, pid, nuevo, usuario):
    return client.patch(f"/api/panel/pedidos/{pid}/estado", json={"estado": nuevo}, headers=headers(usuario))


# ---------- permisos ----------


def test_panel_pide_login(client):
    assert client.get("/api/panel/pedidos").status_code == 401


def test_cocina_ve_pedidos_pero_no_el_resumen(client, cocina, pedido):
    assert client.get("/api/panel/pedidos", headers=headers(cocina)).status_code == 200
    assert client.get("/api/panel/resumen", headers=headers(cocina)).status_code == 403


def test_cocina_no_cobra_ni_reimprime(client, cocina, pedido):
    assert client.post(f"/api/panel/pedidos/{pedido}/cobrar", headers=headers(cocina)).status_code == 403
    assert client.post(f"/api/panel/pedidos/{pedido}/reimprimir", headers=headers(cocina)).status_code == 403


def test_pedido_que_no_existe(client, cantina, carta):
    assert client.get("/api/panel/pedidos/999", headers=headers(cantina)).status_code == 404


# ---------- transiciones ----------


def test_camino_feliz(client, cantina, pedido):
    for nuevo in ["en_preparacion", "listo", "entregado"]:
        r = estado(client, pedido, nuevo, cantina)
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == nuevo


def test_transicion_invalida(client, cantina, pedido):
    r = estado(client, pedido, "listo", cantina)
    assert r.status_code == 400
    assert r.json()["detail"] == "Un pedido recibido no puede pasar a listo"


def test_entregado_no_vuelve(client, db, cantina, pedido):
    db.get(Pedido, pedido).estado = EstadoPedido.entregado
    db.commit()
    assert estado(client, pedido, "recibido", cantina).status_code == 400


def test_mismo_estado_no_hace_nada(client, cantina, pedido):
    assert estado(client, pedido, "recibido", cantina).status_code == 200


def test_cocina_mueve_lo_suyo(client, cocina, pedido):
    assert estado(client, pedido, "en_preparacion", cocina).status_code == 200
    assert estado(client, pedido, "listo", cocina).status_code == 200
    assert estado(client, pedido, "en_preparacion", cocina).status_code == 200


def test_cocina_no_cancela_ni_entrega(client, cocina, cantina, pedido):
    r = estado(client, pedido, "cancelado", cocina)
    assert r.status_code == 400
    assert "Desde la cocina" in r.json()["detail"]
    estado(client, pedido, "en_preparacion", cantina)
    estado(client, pedido, "listo", cantina)
    assert estado(client, pedido, "entregado", cocina).status_code == 400


def test_pendiente_pago_solo_se_cancela_a_mano(client, db, cantina, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    pid = id_de(db, p["codigo"])
    assert estado(client, pid, "recibido", cantina).status_code == 400
    assert estado(client, pid, "cancelado", cantina).status_code == 200


# ---------- cobrar ----------


def test_cobrar_efectivo(client, cantina, pedido):
    r = client.post(f"/api/panel/pedidos/{pedido}/cobrar", headers=headers(cantina))
    assert r.status_code == 200
    assert r.json()["estado_pago"] == "aprobado"
    otra = client.post(f"/api/panel/pedidos/{pedido}/cobrar", headers=headers(cantina))
    assert otra.status_code == 400
    assert otra.json()["detail"] == "Este pedido ya estaba cobrado"


def test_no_se_cobra_un_pedido_de_mp(client, db, cantina, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    r = client.post(f"/api/panel/pedidos/{id_de(db, p['codigo'])}/cobrar", headers=headers(cantina))
    assert r.status_code == 400


def test_no_se_cobra_un_cancelado(client, cantina, pedido):
    estado(client, pedido, "cancelado", cantina)
    r = client.post(f"/api/panel/pedidos/{pedido}/cobrar", headers=headers(cantina))
    assert r.status_code == 400


# ---------- reimprimir ----------


def test_reimprimir_vacia_impreso_at(client, db, cantina, pedido):
    db.get(Pedido, pedido).impreso_at = datetime.now(timezone.utc)
    db.commit()
    r = client.post(f"/api/panel/pedidos/{pedido}/reimprimir", headers=headers(cantina))
    assert r.status_code == 200
    assert r.json()["impreso_at"] is None


def test_no_se_reimprime_un_pendiente_pago(client, db, cantina, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    r = client.post(f"/api/panel/pedidos/{id_de(db, p['codigo'])}/reimprimir", headers=headers(cantina))
    assert r.status_code == 400


# ---------- listado y resumen ----------


def test_listado_activos_y_todos(client, db, cantina, carta):
    a = id_de(db, hacer_pedido(client, db)["codigo"])
    b = id_de(db, hacer_pedido(client, db)["codigo"])
    estado(client, b, "cancelado", cantina)

    activos = client.get("/api/panel/pedidos", headers=headers(cantina)).json()
    assert [p["id"] for p in activos] == [a]
    # La cantina ve el teléfono
    assert activos[0]["telefono"] == "2615550142"

    todos = client.get("/api/panel/pedidos?todos=true", headers=headers(cantina)).json()
    assert [p["id"] for p in todos] == [a, b]

    cancelados = client.get("/api/panel/pedidos?estado=cancelado", headers=headers(cantina)).json()
    assert [p["id"] for p in cancelados] == [b]


def test_resumen(client, db, cantina, carta):
    a = id_de(db, hacer_pedido(client, db)["codigo"])  # 20.000 efectivo sin cobrar
    b = id_de(db, hacer_pedido(client, db)["codigo"])  # 20.000 efectivo cobrado
    c = id_de(db, hacer_pedido(client, db)["codigo"])  # cancelado
    hacer_pedido(client, db, metodo_pago="mercadopago")  # esperando pago
    client.post(f"/api/panel/pedidos/{b}/cobrar", headers=headers(cantina))
    estado(client, c, "cancelado", cantina)

    r = client.get("/api/panel/resumen", headers=headers(cantina)).json()
    assert r == {"pedidos": 2, "vendido": 20000, "efectivo_a_cobrar": 20000, "esperando_pago_mp": 1}
    assert a
