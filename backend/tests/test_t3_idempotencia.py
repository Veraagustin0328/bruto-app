"""A1 (tarea 3): el mismo Idempotency-Key no crea dos pedidos aunque el celu reintente."""
from sqlalchemy import func, select

from app.config import settings
from app.models import Pedido
from app.services import pedidos as srv
from app.schemas.pedido import PedidoNuevo
from tests.conftest import datos_pedido, headers
from tests.test_ws import ws_panel

CLAVE = "3f2b8c1e-9d4a-4e6b-8f1a-2c3d4e5f6a7b"


def pedir(client, db, clave=CLAVE, ip="1.1.1.1", **kw):
    h = {"X-Forwarded-For": ip}
    if clave is not None:
        h["Idempotency-Key"] = clave
    return client.post("/api/tienda/pedidos", json=datos_pedido(db, **kw), headers=h)


def cuantos(db) -> int:
    db.expire_all()
    return db.scalar(select(func.count(Pedido.id)))


def test_dos_post_con_la_misma_clave_crean_un_solo_pedido(client, db, carta):
    r1 = pedir(client, db)
    r2 = pedir(client, db)
    assert r1.status_code == 201
    assert r2.status_code == 200  # no es nuevo: es el que ya estaba
    assert r1.json()["numero"] == r2.json()["numero"]
    assert r1.json()["codigo"] == r2.json()["codigo"]
    assert cuantos(db) == 1


def test_claves_distintas_son_pedidos_distintos(client, db, carta):
    a = pedir(client, db, clave="a" * 36).json()
    b = pedir(client, db, clave="b" * 36).json()
    assert a["numero"] != b["numero"]
    assert cuantos(db) == 2


def test_sin_clave_anda_como_antes(client, db, carta):
    assert pedir(client, db, clave=None).status_code == 201
    assert pedir(client, db, clave=None).status_code == 201
    assert cuantos(db) == 2


def test_el_reintento_no_gasta_el_cupo_por_ip(client, db, carta, monkeypatch):
    monkeypatch.setattr(settings, "limite_pedidos_por_ip", 2)
    assert pedir(client, db).status_code == 201
    # Muchos reintentos del mismo intento: no cuentan
    for _ in range(5):
        assert pedir(client, db).status_code == 200
    # Todavía le queda un pedido de verdad
    assert pedir(client, db, clave="otra-clave-1234", telefono="2615550001").status_code == 201
    assert pedir(client, db, clave="otra-clave-5678", telefono="2615550002").status_code == 429


def test_el_reintento_no_cuenta_para_el_limite_por_telefono(client, db, carta, monkeypatch):
    monkeypatch.setattr(settings, "limite_activos_por_telefono", 1)
    assert pedir(client, db).status_code == 201
    # El teléfono ya llegó al tope, pero es el mismo intento: devuelve el que había
    assert pedir(client, db).status_code == 200
    assert pedir(client, db, clave="otra-clave-1234").status_code == 429


def test_el_reintento_devuelve_el_pedido_aunque_ahora_este_pausado(client, db, carta, admin):
    primero = pedir(client, db).json()
    client.patch("/api/config", json={"pedidos_pausados": True}, headers=headers(admin))
    r = pedir(client, db)
    assert r.status_code == 200
    assert r.json()["numero"] == primero["numero"]
    # Uno nuevo de verdad sí se frena
    assert pedir(client, db, clave="otra-clave-1234").status_code == 400


def test_la_cantina_se_entera_una_sola_vez(client, db, carta, cantina):
    with ws_panel(client, cantina) as ws:
        pedir(client, db)
        pedir(client, db)
        ws.send_text("ping")
        primero = ws.receive_json()
        # Lo que sigue tiene que ser el pong, no otro pedido_nuevo
        assert ws.receive_text() == "pong"
    assert primero["evento"] == "pedido_nuevo"


def test_un_error_no_quema_la_clave(client, db, carta):
    # Si el primer intento falla (ej. producto que no existe), el cliente lo
    # arregla y reintenta con la misma clave: ahí sí se crea
    malo = pedir(client, db, items=[{"producto_id": 9999, "cantidad": 1}])
    assert malo.status_code == 400
    assert pedir(client, db).status_code == 201
    assert cuantos(db) == 1


def test_clave_rara_da_400(client, db, carta):
    assert pedir(client, db, clave="corta").status_code == 400
    assert pedir(client, db, clave="x" * 65).status_code == 400
    assert pedir(client, db, clave="con espacios 123 y; raros").status_code == 400
    assert cuantos(db) == 0


def test_dos_al_mismo_tiempo_con_la_misma_clave(db, carta):
    # Simulo la carrera: el segundo no ve al primero en la búsqueda y choca
    # con el índice único al guardar. Tiene que devolver el primero, no explotar
    datos = PedidoNuevo(**datos_pedido(db))
    primero, nuevo = srv.crear_o_repetir(db, datos, CLAVE)
    assert nuevo

    original = srv.buscar_por_clave
    llamadas = []

    def ciego(db_, clave):
        llamadas.append(clave)
        # La primera búsqueda (antes de crear) no lo ve, como si fuera a la vez
        return None if len(llamadas) == 1 else original(db_, clave)

    srv.buscar_por_clave = ciego
    try:
        segundo, nuevo2 = srv.crear_o_repetir(db, datos, CLAVE)
    finally:
        srv.buscar_por_clave = original
    assert not nuevo2
    assert segundo.id == primero.id
    assert cuantos(db) == 1
