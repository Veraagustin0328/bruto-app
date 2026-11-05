import pytest

from app import limites
from app.config import settings
from app.models import EstadoPedido, Pedido
from tests.conftest import PASSWORD, datos_pedido, id_de


def pedir(client, db, ip="1.1.1.1", telefono=None, **kw):
    datos = datos_pedido(db, **kw)
    if telefono:
        datos["telefono"] = telefono
    return client.post("/api/tienda/pedidos", json=datos, headers={"X-Forwarded-For": ip})


# ---------- pedidos por IP ----------


def test_cinco_pedidos_por_ip_y_el_sexto_no(client, db, carta):
    for i in range(5):
        # Teléfonos distintos, así no salta el límite por teléfono
        assert pedir(client, db, telefono=f"26155500{i:02d}").status_code == 201
    r = pedir(client, db, telefono="2615550099")
    assert r.status_code == 429
    assert r.json()["detail"] == "Hiciste muchos pedidos seguidos, esperá unos minutos"


def test_otra_ip_puede_seguir_pidiendo(client, db, carta):
    for i in range(5):
        pedir(client, db, ip="1.1.1.1", telefono=f"26155500{i:02d}")
    assert pedir(client, db, ip="2.2.2.2", telefono="2615550099").status_code == 201


def test_los_pedidos_con_error_no_gastan_el_cupo(client, db, carta):
    malo = [{"producto_id": 9999, "cantidad": 1}]
    for _ in range(10):
        assert pedir(client, db, items=malo).status_code == 400
    assert pedir(client, db).status_code == 201


def test_la_ventana_se_libera_con_el_tiempo(client, db, carta, monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(limites, "reloj", lambda: ahora[0])
    for i in range(5):
        pedir(client, db, telefono=f"26155500{i:02d}")
    assert pedir(client, db, telefono="2615550099").status_code == 429
    ahora[0] += settings.limite_pedidos_minutos * 60 + 1
    assert pedir(client, db, telefono="2615550099").status_code == 201


def test_limite_de_pedidos_sale_de_config(client, db, carta, monkeypatch):
    monkeypatch.setattr(settings, "limite_pedidos_por_ip", 2)
    pedir(client, db, telefono="2615550001")
    pedir(client, db, telefono="2615550002")
    assert pedir(client, db, telefono="2615550003").status_code == 429


# ---------- IP detrás del proxy ----------


class _Req:
    def __init__(self, headers, host="10.0.0.1"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def test_ip_sin_proxy():
    assert limites.ip_del_cliente(_Req({})) == "10.0.0.1"


def test_ip_de_x_forwarded_for():
    assert limites.ip_del_cliente(_Req({"x-forwarded-for": "200.1.2.3"})) == "200.1.2.3"


def test_ip_trucha_en_x_forwarded_for_no_sirve():
    # El cliente manda "1.1.1.1" inventado y el proxy le agrega la real al final
    req = _Req({"x-forwarded-for": "1.1.1.1, 200.1.2.3"})
    assert limites.ip_del_cliente(req) == "200.1.2.3"


def test_cambiar_el_header_falso_no_saltea_el_limite(client, db, carta):
    for i in range(5):
        pedir(client, db, ip=f"9.9.9.{i}, 200.1.2.3", telefono=f"26155500{i:02d}")
    assert pedir(client, db, ip="8.8.8.8, 200.1.2.3", telefono="2615550099").status_code == 429


# ---------- pedidos activos por teléfono ----------


def test_tres_activos_por_telefono(client, db, carta):
    for i in range(3):
        assert pedir(client, db, ip=f"3.3.3.{i}").status_code == 201
    r = pedir(client, db, ip="3.3.3.9")
    assert r.status_code == 429
    assert "pedidos en curso con este teléfono" in r.json()["detail"]


def test_el_telefono_se_compara_normalizado(client, db, carta):
    for i in range(3):
        pedir(client, db, ip=f"3.3.3.{i}", telefono="261 555-0142")
    assert pedir(client, db, ip="3.3.3.9", telefono="2615550142").status_code == 429


def test_entregados_y_cancelados_no_cuentan(client, db, carta):
    ids = [id_de(db, pedir(client, db, ip=f"3.3.3.{i}").json()["codigo"]) for i in range(3)]
    db.get(Pedido, ids[0]).estado = EstadoPedido.entregado
    db.get(Pedido, ids[1]).estado = EstadoPedido.cancelado
    db.commit()
    assert pedir(client, db, ip="3.3.3.9").status_code == 201


def test_los_de_mp_sin_pagar_no_cuentan(client, db, carta):
    for i in range(3):
        pedir(client, db, ip=f"3.3.3.{i}", metodo_pago="mercadopago")
    assert pedir(client, db, ip="3.3.3.9").status_code == 201


# ---------- login ----------


def login(client, password, email="admin@bruto.com"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def test_cinco_fallidos_bloquean_el_email(client, admin):
    for _ in range(5):
        assert login(client, "mal").status_code == 401
    r = login(client, PASSWORD)  # ni con la clave buena
    assert r.status_code == 429
    assert r.json()["detail"] == "Muchos intentos fallidos. Probá de nuevo en 15 minutos"


def test_el_bloqueo_es_por_email(client, admin, cantina):
    for _ in range(5):
        login(client, "mal")
    assert login(client, PASSWORD, email="cantina@bruto.com").status_code == 200


def test_el_bloqueo_no_distingue_mayusculas(client, admin):
    for _ in range(5):
        login(client, "mal", email="ADMIN@bruto.com")
    assert login(client, PASSWORD).status_code == 429


def test_login_bueno_reinicia_la_cuenta(client, admin):
    for _ in range(4):
        login(client, "mal")
    assert login(client, PASSWORD).status_code == 200
    for _ in range(4):
        login(client, "mal")
    assert login(client, PASSWORD).status_code == 200


def test_el_bloqueo_se_va_a_los_15_minutos(client, admin, monkeypatch):
    ahora = [5000.0]
    monkeypatch.setattr(limites, "reloj", lambda: ahora[0])
    for _ in range(5):
        login(client, "mal")
    ahora[0] += 14 * 60
    assert login(client, PASSWORD).status_code == 429
    ahora[0] += 61
    assert login(client, PASSWORD).status_code == 200


def test_email_que_no_existe_tambien_se_bloquea(client, carta):
    # Así no se puede usar el bloqueo para saber qué emails existen
    for _ in range(5):
        login(client, "mal", email="nadie@bruto.com")
    assert login(client, "mal", email="nadie@bruto.com").status_code == 429


@pytest.mark.parametrize("intentos", [3])
def test_limite_de_login_sale_de_config(client, admin, monkeypatch, intentos):
    monkeypatch.setattr(settings, "login_intentos_max", intentos)
    for _ in range(intentos):
        login(client, "mal")
    assert login(client, PASSWORD).status_code == 429
