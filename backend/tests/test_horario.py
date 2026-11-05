from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.models import Horario
from app.models.config import MENSAJE_CERRADO, MENSAJE_PAUSADO
from app.services import config as srv
from tests.conftest import datos_pedido, headers

MZA = ZoneInfo("America/Argentina/Mendoza")

# El 2 de noviembre de 2026 es lunes
LUNES = 2


def cuando(dia, hora, minuto=0):
    return datetime(2026, 11, dia, hora, minuto, tzinfo=MZA)


@pytest.fixture
def horario_inicial(db):
    # Lo mismo que carga la migración: todos los días de 18:00 a 00:30
    for dia in range(7):
        db.add(Horario(dia_semana=dia, abierto=True, abre=time(18), cierra=time(0, 30)))
    db.commit()


def mover_reloj(monkeypatch, momento):
    monkeypatch.setattr(srv, "ahora_local", lambda: momento)


# ---------- cálculo del horario ----------


@pytest.mark.parametrize("dia,hora,minuto,abierto", [
    (LUNES, 17, 59, False),
    (LUNES, 18, 0, True),
    (LUNES, 23, 59, True),
    (LUNES + 1, 0, 15, True),   # martes 00:15, sigue el turno del lunes
    (LUNES + 1, 0, 30, False),  # martes 00:30, cerró
    (LUNES + 1, 12, 0, False),
])
def test_horario_que_pasa_la_medianoche(db, horario_inicial, dia, hora, minuto, abierto):
    assert srv.esta_en_horario(db, cuando(dia, hora, minuto)) is abierto


def test_dia_que_no_abre(db, horario_inicial):
    db.query(Horario).filter_by(dia_semana=0).one().abierto = False  # lunes cerrado
    db.commit()
    assert srv.esta_en_horario(db, cuando(LUNES, 20)) is False
    # Martes 00:15 era del turno del lunes, que no abrió
    assert srv.esta_en_horario(db, cuando(LUNES + 1, 0, 15)) is False
    assert srv.esta_en_horario(db, cuando(LUNES + 1, 20)) is True


def test_turno_que_no_pasa_la_medianoche(db, horario_inicial):
    dom = db.query(Horario).filter_by(dia_semana=6).one()
    dom.abre, dom.cierra = time(12), time(16)
    db.commit()
    domingo = 8
    assert srv.esta_en_horario(db, cuando(domingo, 13)) is True
    assert srv.esta_en_horario(db, cuando(domingo, 16)) is False
    # Lunes 00:15: el domingo no pasa la medianoche, así que está cerrado
    assert srv.esta_en_horario(db, cuando(domingo + 1, 0, 15)) is False


def test_usa_la_zona_horaria_de_mendoza(db, horario_inicial):
    # 21:00 UTC = 18:00 en Mendoza
    assert srv.esta_en_horario(db, datetime(2026, 11, LUNES, 21, 0, tzinfo=ZoneInfo("UTC"))) is True
    assert srv.esta_en_horario(db, datetime(2026, 11, LUNES, 20, 59, tzinfo=ZoneInfo("UTC"))) is False


def test_sin_horarios_cargados_esta_abierto(db):
    assert srv.esta_en_horario(db, cuando(LUNES, 9)) is True


# ---------- estado público ----------


def test_estado_abierto(client, db, horario_inicial, monkeypatch):
    mover_reloj(monkeypatch, cuando(LUNES, 20))
    r = client.get("/api/tienda/estado")
    assert r.status_code == 200
    assert r.json() == {
        "abierto": True, "pausado": False, "acepta_pedidos": True, "mensaje": None,
        "link_delivery": None,
        "horario_hoy": {"dia_semana": 0, "abierto": True, "abre": "18:00:00", "cierra": "00:30:00"},
    }


def test_estado_cerrado(client, db, horario_inicial, monkeypatch):
    mover_reloj(monkeypatch, cuando(LUNES, 10))
    r = client.get("/api/tienda/estado").json()
    assert r["abierto"] is False and r["acepta_pedidos"] is False
    assert r["mensaje"] == MENSAJE_CERRADO


def test_estado_pausado(client, db, admin, horario_inicial, monkeypatch):
    mover_reloj(monkeypatch, cuando(LUNES, 20))
    client.patch("/api/config", json={"pedidos_pausados": True}, headers=headers(admin))
    r = client.get("/api/tienda/estado").json()
    assert r["abierto"] is True and r["pausado"] is True and r["acepta_pedidos"] is False
    assert r["mensaje"] == MENSAJE_PAUSADO


# ---------- crear pedido según el horario ----------


def test_cerrado_no_acepta_pedidos(client, db, carta, horario_inicial, monkeypatch):
    mover_reloj(monkeypatch, cuando(LUNES, 10))
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db))
    assert r.status_code == 400
    assert r.json()["detail"] == MENSAJE_CERRADO


def test_pausado_no_acepta_pedidos(client, db, admin, carta, horario_inicial, monkeypatch):
    mover_reloj(monkeypatch, cuando(LUNES, 20))
    client.patch("/api/config", json={"pedidos_pausados": True, "mensaje_pausado": "Volvemos en 10"}, headers=headers(admin))
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db))
    assert r.status_code == 400 and r.json()["detail"] == "Volvemos en 10"

    client.patch("/api/config", json={"pedidos_pausados": False}, headers=headers(admin))
    assert client.post("/api/tienda/pedidos", json=datos_pedido(db)).status_code == 201


def test_abierto_pasada_la_medianoche_acepta(client, db, carta, horario_inicial, monkeypatch):
    mover_reloj(monkeypatch, cuando(LUNES + 1, 0, 10))
    assert client.post("/api/tienda/pedidos", json=datos_pedido(db)).status_code == 201


# ---------- configuración (solo admin) ----------


def test_config_solo_admin(client, cantina, cocina):
    for u in (cantina, cocina):
        assert client.get("/api/config", headers=headers(u)).status_code == 403
        assert client.patch("/api/config", json={"pedidos_pausados": True}, headers=headers(u)).status_code == 403


def test_ver_y_editar_config(client, admin, horario_inicial):
    h = headers(admin)
    r = client.get("/api/config", headers=h).json()
    assert r["pedidos_pausados"] is False and len(r["horarios"]) == 7

    r = client.patch("/api/config", json={"link_pedidosya": " https://www.pedidosya.com.ar/bruto "}, headers=h).json()
    assert r["link_pedidosya"] == "https://www.pedidosya.com.ar/bruto"
    assert client.get("/api/tienda/estado").json()["link_delivery"] == "https://www.pedidosya.com.ar/bruto"

    # Mandar otra cosa no borra el link; mandarlo en null sí
    r = client.patch("/api/config", json={"mensaje_cerrado": "Cerrado, volvé a la noche"}, headers=h).json()
    assert r["link_pedidosya"] == "https://www.pedidosya.com.ar/bruto"
    assert r["mensaje_cerrado"] == "Cerrado, volvé a la noche"
    r = client.patch("/api/config", json={"link_pedidosya": None}, headers=h).json()
    assert r["link_pedidosya"] is None


def test_link_tiene_que_ser_https(client, admin):
    r = client.patch("/api/config", json={"link_pedidosya": "pedidosya.com/bruto"}, headers=headers(admin))
    assert r.status_code == 422


def semana(abre="18:00", cierra="00:30", **cambios):
    dias = [{"dia_semana": d, "abierto": True, "abre": abre, "cierra": cierra} for d in range(7)]
    for d, valores in cambios.items():
        dias[int(d[1:])].update(valores)
    return {"dias": dias}


def test_cambiar_horarios(client, db, admin, horario_inicial, monkeypatch):
    cuerpo = semana(abre="19:00", cierra="01:00", d0={"abierto": False})
    r = client.put("/api/config/horarios", json=cuerpo, headers=headers(admin))
    assert r.status_code == 200, r.text
    assert r.json()["horarios"][0]["abierto"] is False
    assert r.json()["horarios"][1]["abre"] == "19:00:00"

    mover_reloj(monkeypatch, cuando(LUNES + 1, 0, 45))  # martes 00:45, el lunes no abrió
    assert client.get("/api/tienda/estado").json()["abierto"] is False
    mover_reloj(monkeypatch, cuando(LUNES + 2, 0, 45))  # miércoles 00:45, turno del martes hasta la 01:00
    assert client.get("/api/tienda/estado").json()["abierto"] is True


def test_cargar_horarios_en_base_vacia(client, db, admin):
    r = client.put("/api/config/horarios", json=semana(), headers=headers(admin))
    assert r.status_code == 200 and len(r.json()["horarios"]) == 7


@pytest.mark.parametrize("cuerpo", [
    {"dias": semana()["dias"][:6]},  # falta un día
    {"dias": semana()["dias"][:6] + [semana()["dias"][0]]},  # lunes repetido
    semana(abre="18:00", cierra="18:00"),  # abre y cierra igual
])
def test_horarios_mal_armados(client, admin, cuerpo):
    assert client.put("/api/config/horarios", json=cuerpo, headers=headers(admin)).status_code == 422


def test_horarios_solo_admin(client, cantina):
    assert client.put("/api/config/horarios", json=semana(), headers=headers(cantina)).status_code == 403
