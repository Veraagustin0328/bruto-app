from app.models import Rol
from tests.conftest import PASSWORD, crear_usuario, headers


def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def test_login_ok(client, admin):
    r = login(client, "  ADMIN@bruto.com ")
    assert r.status_code == 200
    assert r.json()["usuario"]["rol"] == "admin"
    token = r.json()["access_token"]
    yo = client.get("/api/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert yo.json()["email"] == "admin@bruto.com"


def test_login_clave_mal(client, admin):
    r = login(client, "admin@bruto.com", "otra-cosa")
    assert r.status_code == 401
    assert r.json()["detail"] == "Email o contraseña incorrectos"


def test_login_email_que_no_existe_mismo_mensaje(client, admin):
    r = login(client, "nadie@bruto.com")
    assert r.status_code == 401
    assert r.json()["detail"] == "Email o contraseña incorrectos"


def test_login_usuario_dado_de_baja(client, db):
    crear_usuario(db, Rol.cantina, activo=False)
    assert login(client, "cantina@bruto.com").status_code == 403


def test_sin_token_401(client):
    assert client.get("/api/auth/yo").status_code == 401


def test_token_trucho_401(client):
    r = client.get("/api/auth/yo", headers={"Authorization": "Bearer cualquiera"})
    assert r.status_code == 401


def test_token_de_usuario_dado_de_baja_deja_de_andar(client, db, cantina):
    h = headers(cantina)
    assert client.get("/api/auth/yo", headers=h).status_code == 200
    cantina.activo = False
    db.commit()
    assert client.get("/api/auth/yo", headers=h).status_code == 401


def test_usuarios_solo_admin(client, admin, cantina, cocina):
    assert client.get("/api/auth/usuarios", headers=headers(admin)).status_code == 200
    assert client.get("/api/auth/usuarios", headers=headers(cantina)).status_code == 403
    assert client.get("/api/auth/usuarios", headers=headers(cocina)).status_code == 403


def test_crear_usuario(client, admin):
    nuevo = {"nombre": "Lucas", "email": "Lucas@Bruto.com", "password": "12345678", "rol": "cocina"}
    r = client.post("/api/auth/usuarios", json=nuevo, headers=headers(admin))
    assert r.status_code == 201
    assert r.json()["email"] == "lucas@bruto.com"
    assert login(client, "lucas@bruto.com", "12345678").status_code == 200

    otra_vez = client.post("/api/auth/usuarios", json=nuevo, headers=headers(admin))
    assert otra_vez.status_code == 409


def test_editar_usuario(client, admin, cantina):
    r = client.patch(
        f"/api/auth/usuarios/{cantina.id}", json={"rol": "cocina"}, headers=headers(admin)
    )
    assert r.status_code == 200 and r.json()["rol"] == "cocina"


def test_admin_no_se_puede_sacar_el_admin(client, admin):
    r = client.patch(f"/api/auth/usuarios/{admin.id}", json={"activo": False}, headers=headers(admin))
    assert r.status_code == 400
    r = client.patch(f"/api/auth/usuarios/{admin.id}", json={"rol": "cantina"}, headers=headers(admin))
    assert r.status_code == 400


def test_editar_usuario_que_no_existe(client, admin):
    r = client.patch("/api/auth/usuarios/999", json={"nombre": "Pepe"}, headers=headers(admin))
    assert r.status_code == 404
