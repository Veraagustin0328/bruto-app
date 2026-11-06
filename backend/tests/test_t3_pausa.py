"""B3 (tarea 3): la cantina también puede pausar los pedidos."""
import pytest

from app.models import Rol
from tests.conftest import crear_usuario, datos_pedido, headers
from tests.test_ws import ws_panel


def pausar(client, usuario, valor=True):
    return client.put("/api/config/pausa", json={"pausado": valor}, headers=headers(usuario))


def test_la_cantina_pausa_y_la_tienda_no_acepta_pedidos(client, db, carta, cantina):
    r = pausar(client, cantina)
    assert r.status_code == 200, r.text
    assert r.json()["pedidos_pausados"] is True
    assert "pausamos" in r.json()["mensaje_pausado"].lower()

    estado = client.get("/api/tienda/estado").json()
    assert estado["pausado"] is True and estado["acepta_pedidos"] is False
    assert client.post("/api/tienda/pedidos", json=datos_pedido(db)).status_code == 400

    # Y la despausa
    assert pausar(client, cantina, False).json()["pedidos_pausados"] is False
    assert client.post("/api/tienda/pedidos", json=datos_pedido(db)).status_code == 201


def test_el_admin_tambien_pausa(client, admin):
    assert pausar(client, admin).status_code == 200
    assert client.get("/api/config/pausa", headers=headers(admin)).json()["pedidos_pausados"] is True


def test_la_cantina_ve_la_pausa(client, cantina):
    r = client.get("/api/config/pausa", headers=headers(cantina))
    assert r.status_code == 200
    assert r.json()["pedidos_pausados"] is False


@pytest.mark.parametrize("rol", [Rol.cocina, Rol.impresora])
def test_cocina_e_impresora_no_pausan(client, db, rol):
    u = crear_usuario(db, rol)
    assert pausar(client, u).status_code == 403
    assert client.get("/api/config/pausa", headers=headers(u)).status_code == 403


def test_sin_login_no_pausa(client):
    assert client.put("/api/config/pausa", json={"pausado": True}).status_code == 401


def test_la_cantina_sigue_sin_poder_tocar_el_resto(client, cantina):
    # El horario, el link y los mensajes siguen siendo cosa de Renzo
    assert client.patch("/api/config", json={"pedidos_pausados": True}, headers=headers(cantina)).status_code == 403
    assert client.get("/api/config", headers=headers(cantina)).status_code == 403


def test_pausar_avisa_a_los_paneles(client, cantina, cocina):
    with ws_panel(client, cocina) as ws:
        pausar(client, cantina)
        assert ws.receive_json() == {"evento": "config_actualizada"}


def test_cambiar_config_avisa_a_los_paneles(client, admin, cantina):
    with ws_panel(client, cantina) as ws:
        client.patch("/api/config", json={"link_pedidosya": "https://pedidosya.com.ar/bruto"}, headers=headers(admin))
        assert ws.receive_json() == {"evento": "config_actualizada"}
