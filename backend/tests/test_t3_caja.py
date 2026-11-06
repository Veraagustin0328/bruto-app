"""C1 (tarea 3): caja del día y el historial.

Los pedidos se arman a mano con su hora, así se prueba bien el corte de
las 6 de la mañana. El jueves 5/11/2026 la jornada va del jueves 6:00
al viernes 6:00 (hora de Mendoza, UTC-3)
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    EstadoPago as EP,
    EstadoPedido as E,
    MetodoPago as M,
    ModoPedido as Modo,
    Pedido,
    PedidoItem,
    Rol,
)
from app.services import caja as srv
from tests.conftest import crear_usuario, headers

MZA = ZoneInfo("America/Argentina/Mendoza")
JUEVES = date(2026, 11, 5)
_numero = [0]


def hora(dia, h, m=0):
    return datetime(2026, 11, dia, h, m, tzinfo=MZA)


def pedido(db, cuando, estado, metodo, estado_pago, modo=Modo.comer_adentro, items=(("Animal", 20000, 1),)):
    _numero[0] += 1
    total = sum(Decimal(precio) * cant for _, precio, cant in items)
    p = Pedido(
        numero=_numero[0],
        modo=modo,
        ubicacion="Cancha 1" if modo == Modo.comer_adentro else None,
        nombre="Ana",
        apellido="Test",
        telefono="2615550000",
        metodo_pago=metodo,
        estado_pago=estado_pago,
        estado=estado,
        total=total,
        # En UTC, como lo guarda la app: SQLite no guarda la zona horaria
        created_at=cuando.astimezone(timezone.utc),
        items=[PedidoItem(nombre_producto=n, precio_unitario=Decimal(pr), cantidad=c) for n, pr, c in items],
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def jornada(db):
    # Jueves 5/11 (de 6:00 a 6:00 del viernes)
    pedido(db, hora(5, 20, 15), E.recibido, M.mercadopago, EP.aprobado)  # 20.000 MP
    pedido(db, hora(5, 21, 40), E.entregado, M.efectivo, EP.aprobado, Modo.take_away, (("Clásica", 12500, 1),))
    pedido(db, hora(5, 21, 50), E.listo, M.efectivo, EP.pendiente, items=(("Papas Fritas", 9000, 1),))  # falta cobrar
    pedido(db, hora(5, 22, 0), E.cancelado, M.efectivo, EP.pendiente, items=(("Lomo Clásico", 19000, 1),))
    pedido(db, hora(5, 22, 10), E.cancelado, M.mercadopago, EP.pendiente)  # MP que nadie pagó
    pedido(db, hora(5, 22, 20), E.pendiente_pago, M.mercadopago, EP.pendiente)  # todavía esperando el pago
    pedido(db, hora(6, 0, 30), E.entregado, M.mercadopago, EP.aprobado, items=(("Papas Fritas", 7500, 2),))  # 15.000, madrugada
    pedido(db, hora(6, 5, 59), E.entregado, M.efectivo, EP.aprobado, Modo.take_away, (("Super Pancho", 4000, 1),))
    # Otras jornadas
    pedido(db, hora(5, 5, 59), E.entregado, M.efectivo, EP.aprobado, items=(("Muzzarella", 14000, 1),))  # es del miércoles
    pedido(db, hora(6, 6, 0), E.entregado, M.mercadopago, EP.aprobado, items=(("Especial", 16000, 1),))  # es del viernes


@pytest.fixture
def es_jueves(monkeypatch):
    monkeypatch.setattr(srv, "ahora", lambda: hora(5, 23, 0))


def caja(client, usuario, fecha=None):
    url = "/api/panel/caja" + (f"?fecha={fecha}" if fecha else "")
    return client.get(url, headers=headers(usuario))


# ---------- caja del día ----------


def test_los_numeros_del_jueves(client, admin, jornada):
    r = caja(client, admin, "2026-11-05")
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["fecha"] == "2026-11-05"
    assert c["pedidos"] == 5  # sin cancelados ni MP sin pagar
    assert c["vendido"] == 51500  # 20.000 + 12.500 + 15.000 + 4.000
    assert c["mercadopago"] == 35000
    assert c["efectivo_cobrado"] == 16500
    assert c["efectivo_a_cobrar"] == 9000
    assert c["ticket_promedio"] == 12100  # (51.500 + 9.000) / 5
    assert c["cancelados"] == 1
    assert c["mp_sin_pagar"] == 1


def test_por_modo(client, admin, jornada):
    modos = {m["modo"]: m for m in caja(client, admin, "2026-11-05").json()["por_modo"]}
    assert modos["comer_adentro"] == {"modo": "comer_adentro", "pedidos": 3, "total": 44000}
    assert modos["take_away"] == {"modo": "take_away", "pedidos": 2, "total": 16500}


def test_productos_mas_vendidos(client, admin, jornada):
    prods = caja(client, admin, "2026-11-05").json()["productos"]
    assert [(p["nombre"], p["cantidad"], p["total"]) for p in prods] == [
        ("Papas Fritas", 3, 24000),  # 1 × 9.000 + 2 × 7.500
        ("Animal", 1, 20000),
        ("Clásica", 1, 12500),
        ("Super Pancho", 1, 4000),
    ]
    # El Lomo del pedido cancelado no cuenta


def test_solo_los_diez_primeros(client, admin, db):
    items = tuple((f"Producto {i:02d}", 1000, i + 1) for i in range(12))
    pedido(db, hora(5, 21), E.entregado, M.efectivo, EP.aprobado, items=items)
    prods = caja(client, admin, "2026-11-05").json()["productos"]
    assert len(prods) == 10
    assert prods[0]["nombre"] == "Producto 11" and prods[0]["cantidad"] == 12


def test_ventas_por_hora(client, admin, jornada):
    horas = caja(client, admin, "2026-11-05").json()["por_hora"]
    assert [h["hora"] for h in horas] == list(range(6, 24)) + list(range(0, 6))  # orden de la jornada
    por = {h["hora"]: (h["pedidos"], h["total"]) for h in horas}
    assert por[20] == (1, 20000)
    assert por[21] == (2, 21500)
    assert por[22] == (0, 0)  # los de las 22 son cancelados o sin pagar
    assert por[0] == (1, 15000)
    assert por[5] == (1, 4000)
    assert sum(h["pedidos"] for h in horas) == 5


def test_el_corte_es_a_las_seis(client, admin, jornada):
    miercoles = caja(client, admin, "2026-11-04").json()
    viernes = caja(client, admin, "2026-11-06").json()
    assert (miercoles["pedidos"], miercoles["vendido"]) == (1, 14000)  # el de las 5:59 del jueves
    assert (viernes["pedidos"], viernes["vendido"]) == (1, 16000)  # el de las 6:00 del viernes


def test_dia_sin_pedidos(client, admin, jornada):
    c = caja(client, admin, "2026-10-01").json()
    assert c["pedidos"] == 0 and c["vendido"] == 0 and c["ticket_promedio"] == 0
    assert c["productos"] == []
    assert all(h["pedidos"] == 0 for h in c["por_hora"])


def test_sin_fecha_es_la_jornada_de_hoy(client, admin, jornada, es_jueves):
    assert caja(client, admin).json()["fecha"] == "2026-11-05"


def test_a_la_madrugada_sigue_siendo_la_jornada_de_ayer(client, admin, jornada, monkeypatch):
    monkeypatch.setattr(srv, "ahora", lambda: hora(6, 1, 30))  # viernes 1:30
    assert caja(client, admin).json()["fecha"] == "2026-11-05"


def test_cantina_ve_la_de_hoy(client, cantina, jornada, es_jueves):
    r = caja(client, cantina)
    assert r.status_code == 200
    assert r.json()["vendido"] == 51500
    assert caja(client, cantina, "2026-11-05").status_code == 200


def test_cantina_no_ve_otros_dias(client, cantina, jornada, es_jueves):
    r = caja(client, cantina, "2026-11-04")
    assert r.status_code == 403
    assert r.json()["detail"] == "La cantina solo puede ver la caja de hoy"


def test_cocina_no_ve_la_caja(client, db, jornada):
    assert caja(client, crear_usuario(db, Rol.cocina)).status_code == 403


def test_sin_login_no(client):
    assert client.get("/api/panel/caja").status_code == 401


def test_fecha_mal_escrita(client, admin):
    assert caja(client, admin, "5/11/2026").status_code == 422


# ---------- historial ----------


def hist(client, usuario, **q):
    url = "/api/panel/caja/historial"
    if q:
        url += "?" + "&".join(f"{k}={v}" for k, v in q.items())
    return client.get(url, headers=headers(usuario))


def test_historial_por_dia(client, admin, jornada):
    r = hist(client, admin, desde="2026-11-04", hasta="2026-11-06")
    assert r.status_code == 200, r.text
    h = r.json()
    assert [(d["fecha"], d["pedidos"], d["vendido"]) for d in h["dias"]] == [
        ("2026-11-04", 1, 14000),
        ("2026-11-05", 5, 51500),
        ("2026-11-06", 1, 16000),
    ]
    jueves = h["dias"][1]
    assert (jueves["mercadopago"], jueves["efectivo_cobrado"], jueves["cancelados"], jueves["mp_sin_pagar"]) == (35000, 16500, 1, 1)
    assert h["totales"]["pedidos"] == 7
    assert h["totales"]["vendido"] == 81500


def test_historial_por_defecto_son_30_dias(client, admin, jornada, es_jueves):
    h = hist(client, admin).json()
    assert len(h["dias"]) == 30
    assert h["hasta"] == "2026-11-05"
    assert h["desde"] == str(JUEVES - timedelta(days=29))
    # Los días sin pedidos aparecen igual, en cero
    assert h["dias"][0]["pedidos"] == 0


def test_historial_solo_admin(client, cantina, jornada):
    assert hist(client, cantina).status_code == 403


def test_historial_rango_al_reves(client, admin):
    r = hist(client, admin, desde="2026-11-06", hasta="2026-11-01")
    assert r.status_code == 400


def test_historial_rango_muy_largo(client, admin):
    assert hist(client, admin, desde="2024-01-01", hasta="2026-01-01").status_code == 400
