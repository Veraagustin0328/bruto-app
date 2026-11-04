from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import Pedido
from app.services.pedidos import inicio_jornada
from tests.conftest import hacer_pedido

MZA = ZoneInfo("America/Argentina/Mendoza")


def test_jornada_antes_de_las_6_es_la_del_dia_anterior():
    ahora = datetime(2026, 11, 4, 1, 30, tzinfo=MZA)
    assert inicio_jornada(ahora) == datetime(2026, 11, 3, 6, 0, tzinfo=MZA)


def test_jornada_desde_las_6_es_la_del_dia():
    assert inicio_jornada(datetime(2026, 11, 4, 6, 0, tzinfo=MZA)) == datetime(2026, 11, 4, 6, 0, tzinfo=MZA)
    assert inicio_jornada(datetime(2026, 11, 4, 23, 59, tzinfo=MZA)) == datetime(2026, 11, 4, 6, 0, tzinfo=MZA)


def test_jornada_con_hora_en_utc():
    # 03:00 UTC = 00:00 en Mendoza, sigue siendo la jornada del día anterior
    ahora = datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
    assert inicio_jornada(ahora) == datetime(2026, 11, 3, 6, 0, tzinfo=MZA)


def test_numeros_correlativos(client, db, carta):
    numeros = [hacer_pedido(client, db)["numero"] for _ in range(3)]
    assert numeros == [1, 2, 3]


def test_mp_y_efectivo_comparten_numeracion(client, db, carta):
    a = hacer_pedido(client, db, metodo_pago="mercadopago")
    b = hacer_pedido(client, db, metodo_pago="efectivo")
    assert (a["numero"], b["numero"]) == (1, 2)


def test_la_numeracion_arranca_de_nuevo_en_cada_jornada(client, db, carta):
    # Un pedido de anoche con el #057
    ayer = inicio_jornada() - timedelta(hours=1)
    db.add(
        Pedido(
            numero=57, modo="take_away", nombre="Ana", apellido="Gómez", telefono="2615550000",
            metodo_pago="efectivo", estado="entregado", total=1000, created_at=ayer,
        )
    )
    db.commit()
    assert hacer_pedido(client, db)["numero"] == 1


def test_pedido_de_esta_jornada_sigue_la_cuenta(client, db, carta):
    hoy = inicio_jornada() + timedelta(minutes=1)
    db.add(
        Pedido(
            numero=41, modo="take_away", nombre="Ana", apellido="Gómez", telefono="2615550000",
            metodo_pago="efectivo", estado="entregado", total=1000, created_at=hoy,
        )
    )
    db.commit()
    assert hacer_pedido(client, db)["numero"] == 42
