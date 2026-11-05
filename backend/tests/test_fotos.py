from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import storage
from app.config import settings
from tests.conftest import headers, producto
from tests.test_ws import ws_panel


def imagen(formato="JPEG", tam=(1600, 1200), modo="RGB", exif_orientacion=None) -> bytes:
    img = Image.new(modo, tam, (240, 92, 43) if modo == "RGB" else None)
    buf = BytesIO()
    kwargs = {}
    if exif_orientacion:
        exif = Image.Exif()
        exif[0x0112] = exif_orientacion
        kwargs["exif"] = exif
    img.save(buf, formato, **kwargs)
    return buf.getvalue()


def subir(client, admin, pid, contenido, nombre="foto.jpg", tipo="image/jpeg"):
    return client.post(
        f"/api/carta/productos/{pid}/foto",
        files={"foto": (nombre, contenido, tipo)},
        headers=headers(admin),
    )


def archivo_de(url: str) -> Path:
    return Path(settings.uploads_dir) / url.split("/uploads/", 1)[1]


def abrir(url) -> Image.Image:
    return Image.open(archivo_de(url))


def test_sube_achica_y_convierte_a_webp(client, db, admin, carta):
    pid = producto(db, "Animal").id
    r = subir(client, admin, pid, imagen("JPEG", (1600, 1200)))
    assert r.status_code == 200, r.text
    url = r.json()["imagen_url"]
    assert url.startswith("http://localhost:8001/uploads/productos/") and url.endswith(".webp")

    img = abrir(url)
    assert img.format == "WEBP"
    assert img.size == (800, 600)  # mantiene la proporción

    # Y se ve en el menú de la tienda
    menu = client.get("/api/tienda/menu").json()
    animal = next(p for c in menu for p in c["productos"] if p["id"] == pid)
    assert animal["imagen_url"] == url


def test_la_foto_se_sirve(client, db, admin, carta):
    url = subir(client, admin, producto(db, "Animal").id, imagen()).json()["imagen_url"]
    r = client.get(url.replace("http://localhost:8001", ""))
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"


@pytest.mark.parametrize("formato,nombre,tipo", [("PNG", "f.png", "image/png"), ("WEBP", "f.webp", "image/webp")])
def test_acepta_png_y_webp(client, db, admin, carta, formato, nombre, tipo):
    r = subir(client, admin, producto(db, "Animal").id, imagen(formato), nombre, tipo)
    assert r.status_code == 200
    assert abrir(r.json()["imagen_url"]).format == "WEBP"


def test_png_con_transparencia(client, db, admin, carta):
    r = subir(client, admin, producto(db, "Animal").id, imagen("PNG", (300, 300), "RGBA"), "f.png", "image/png")
    assert r.status_code == 200
    assert abrir(r.json()["imagen_url"]).mode == "RGBA"


def test_foto_chica_no_se_agranda(client, db, admin, carta):
    r = subir(client, admin, producto(db, "Animal").id, imagen("JPEG", (400, 300)))
    assert abrir(r.json()["imagen_url"]).size == (400, 300)


def test_foto_vertical(client, db, admin, carta):
    r = subir(client, admin, producto(db, "Animal").id, imagen("JPEG", (1000, 2000)))
    assert abrir(r.json()["imagen_url"]).size == (400, 800)


def test_foto_girada_del_celu_se_endereza(client, db, admin, carta):
    # Orientación 6 = el celu la sacó parado: hay que rotarla
    r = subir(client, admin, producto(db, "Animal").id, imagen("JPEG", (1600, 1200), exif_orientacion=6))
    assert abrir(r.json()["imagen_url"]).size == (600, 800)


def test_mas_de_5_mb(client, db, admin, carta):
    r = subir(client, admin, producto(db, "Animal").id, b"x" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 400
    assert r.json()["detail"] == "La foto pesa más de 5 MB"


def test_archivo_que_no_es_foto(client, db, admin, carta):
    r = subir(client, admin, producto(db, "Animal").id, b"%PDF-1.4 esto no es una foto", "f.jpg")
    assert r.status_code == 400


def test_formato_no_permitido(client, db, admin, carta):
    r = subir(client, admin, producto(db, "Animal").id, imagen("GIF"), "f.gif", "image/gif")
    assert r.status_code == 400
    assert r.json()["detail"] == "La foto tiene que ser jpg, png o webp"


def test_archivo_vacio(client, db, admin, carta):
    assert subir(client, admin, producto(db, "Animal").id, b"").status_code == 400


def test_cambiar_la_foto_borra_la_vieja(client, db, admin, carta):
    pid = producto(db, "Animal").id
    vieja = subir(client, admin, pid, imagen()).json()["imagen_url"]
    nueva = subir(client, admin, pid, imagen()).json()["imagen_url"]
    assert vieja != nueva
    assert not archivo_de(vieja).exists()
    assert archivo_de(nueva).exists()


def test_borrar_la_foto(client, db, admin, carta):
    pid = producto(db, "Animal").id
    url = subir(client, admin, pid, imagen()).json()["imagen_url"]
    r = client.delete(f"/api/carta/productos/{pid}/foto", headers=headers(admin))
    assert r.status_code == 200 and r.json()["imagen_url"] is None
    assert not archivo_de(url).exists()


def test_borrar_el_producto_borra_la_foto(client, db, admin, carta):
    pid = producto(db, "Animal").id
    url = subir(client, admin, pid, imagen()).json()["imagen_url"]
    client.delete(f"/api/carta/productos/{pid}", headers=headers(admin))
    assert not archivo_de(url).exists()


def test_solo_admin(client, db, cantina, carta):
    r = subir(client, cantina, producto(db, "Animal").id, imagen())
    assert r.status_code == 403


def test_producto_que_no_existe(client, admin, carta):
    assert subir(client, admin, 999, imagen()).status_code == 404


def test_subir_foto_avisa_al_panel(client, db, admin, cantina, carta):
    with ws_panel(client, cantina) as ws:
        subir(client, admin, producto(db, "Animal").id, imagen())
        assert ws.receive_json() == {"evento": "carta_actualizada"}


def test_borrar_archivo_no_sale_de_uploads(tmp_path):
    # Un archivo afuera de uploads no se toca aunque armen la URL con "../"
    afuera = Path(settings.uploads_dir).parent / "no-borrar.txt"
    afuera.write_text("hola")
    storage.borrar_archivo(f"{settings.backend_url}/uploads/../no-borrar.txt")
    assert afuera.exists()
    afuera.unlink()


def test_borrar_archivo_ajeno_no_hace_nada():
    storage.borrar_archivo("https://otro-sitio.com/foto.jpg")
    storage.borrar_archivo(None)
