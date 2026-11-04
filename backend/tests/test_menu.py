from tests.conftest import producto


def test_menu_trae_las_categorias_en_orden(client, carta):
    r = client.get("/api/tienda/menu")
    assert r.status_code == 200
    nombres = [c["nombre"] for c in r.json()]
    assert nombres == ["Smash Burgers", "Sandwiches Ahumados", "Pizzas", "Para Picar"]


def test_menu_trae_grupos_y_opciones(client, carta):
    burgers = client.get("/api/tienda/menu").json()[0]
    animal = next(p for p in burgers["productos"] if p["nombre"] == "Animal")
    assert animal["precio"] == 13500
    assert animal["etiqueta"] == "Recomendada"
    tamanio = animal["grupos"][0]
    assert tamanio["nombre"] == "Tamaño" and tamanio["obligatorio"] is True
    doble = next(o for o in tamanio["opciones"] if o["nombre"] == "Doble")
    assert doble["precio_extra"] == 1500
    extra = animal["grupos"][1]["opciones"][0]
    assert extra["cantidad_max"] is None


def test_pepperoni_se_ve_pero_apagada(client, carta):
    pizzas = client.get("/api/tienda/menu").json()[2]
    pepperoni = next(p for p in pizzas["productos"] if p["nombre"] == "Pepperoni")
    assert pepperoni["disponible"] is False


def test_no_visibles_y_categorias_inactivas_no_salen(client, carta, db):
    producto(db, "Lomo Clásico").visible = False
    producto(db, "Muzzarella").categoria.activa = False
    db.commit()

    menu = client.get("/api/tienda/menu").json()
    assert "Pizzas" not in [c["nombre"] for c in menu]
    ahumados = next(c for c in menu if c["nombre"] == "Sandwiches Ahumados")
    assert "Lomo Clásico" not in [p["nombre"] for p in ahumados["productos"]]


def test_categoria_sin_productos_visibles_no_sale(client, carta, db):
    for p in producto(db, "Papas Fritas").categoria.productos:
        p.visible = False
    db.commit()
    menu = client.get("/api/tienda/menu").json()
    assert "Para Picar" not in [c["nombre"] for c in menu]
