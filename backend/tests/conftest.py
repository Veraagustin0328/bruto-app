"""
Todo lo compartido de los tests.

Usan SQLite en memoria: no tocan el Postgres de Docker ni el .env.
Las variables de entorno van antes de importar la app, así pisan lo que haya en el .env
"""
import os

os.environ.update(
    DATABASE_URL="sqlite://",
    JWT_SECRET="secreto-de-los-tests-largo-para-que-no-chille-jwt",
    MP_ACCESS_TOKEN="",
    MP_WEBHOOK_SECRET="",
    FRONTEND_URL="http://localhost:5173",
    BACKEND_URL="http://localhost:8001",
)

import bcrypt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app import database  # noqa: E402
from app.database import Base, SessionLocal  # noqa: E402
from app.models import Opcion, Producto, Rol, Usuario  # noqa: E402
from app.security import crear_token  # noqa: E402

# Una sola conexión compartida, si no cada sesión vería una base vacía distinta
engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
SessionLocal.configure(bind=engine)
database.engine = engine

PASSWORD = "clave-de-prueba"
# bcrypt es lento a propósito. En los tests uso pocas rondas: checkpw lee
# las rondas del hash, así que verificar_password anda igual pero rápido
HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture(autouse=True)
def base_limpia():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def limpiar_memoria():
    # Lo que vive en memoria (límites) arranca de cero en cada test
    from app import limites

    limites.reiniciar()
    yield


@pytest.fixture
def db():
    with SessionLocal() as sesion:
        yield sesion


@pytest.fixture
def client():
    from app.main import app

    # Con "with" corre el lifespan y todo va en el mismo event loop,
    # así los avisos por WebSocket llegan
    with TestClient(app) as c:
        yield c


@pytest.fixture
def carta(db):
    # La carta real de BRUTO, la misma del seed
    from scripts.seed import armar_carta

    db.add_all(armar_carta())
    db.commit()


def producto(db, nombre) -> Producto:
    return db.scalar(select(Producto).where(Producto.nombre == nombre))


def opcion(db, nombre_producto, nombre_opcion) -> Opcion:
    p = producto(db, nombre_producto)
    return next(o for g in p.grupos for o in g.opciones if o.nombre == nombre_opcion)


def crear_usuario(db, rol: Rol, email=None, activo=True) -> Usuario:
    u = Usuario(
        nombre=rol.value.title(),
        email=email or f"{rol.value}@bruto.com",
        password_hash=HASH,
        rol=rol,
        activo=activo,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def headers(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {crear_token(usuario.id, usuario.rol.value)}"}


@pytest.fixture
def admin(db):
    return crear_usuario(db, Rol.admin)


@pytest.fixture
def cantina(db):
    return crear_usuario(db, Rol.cantina)


@pytest.fixture
def cocina(db):
    return crear_usuario(db, Rol.cocina)


@pytest.fixture
def mp(monkeypatch):
    # Mercado Pago simulado, con un token de prueba trucho
    from app.config import settings
    from app.services import pagos
    from tests.mp_falso import MPFalso

    falso = MPFalso()
    monkeypatch.setattr(settings, "mp_access_token", "TEST-token-de-mentira")
    monkeypatch.setattr(pagos, "cliente_mp", lambda: falso)
    return falso


def datos_pedido(db, metodo_pago="efectivo", items=None, **cambios) -> dict:
    # Un pedido típico: una Animal doble con 2 extra carne, para comer adentro
    if items is None:
        items = [
            {
                "producto_id": producto(db, "Animal").id,
                "cantidad": 1,
                "opciones": [
                    {"opcion_id": opcion(db, "Animal", "Doble").id},
                    {"opcion_id": opcion(db, "Animal", "Extra carne y queso").id, "cantidad": 2},
                ],
            }
        ]
    datos = {
        "modo": "comer_adentro",
        "ubicacion": "frente a la cancha 3",
        "nombre": "Juan",
        "apellido": "Pérez",
        "telefono": "261 555-0142",
        "metodo_pago": metodo_pago,
        "items": items,
    }
    datos.update(cambios)
    return datos


def hacer_pedido(client, db, **kwargs) -> dict:
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db, **kwargs))
    assert r.status_code == 201, r.text
    return r.json()


def id_de(db, codigo) -> int:
    from app.models import Pedido

    return db.scalar(select(Pedido.id).where(Pedido.codigo == codigo))
