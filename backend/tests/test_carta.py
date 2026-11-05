from decimal import Decimal

import pytest

from app.models import Categoria, Opcion, Producto
from app.services.carta import redondear
from tests.conftest import hacer_pedido, headers, opcion, producto
from tests.test_ws import ws_panel


def cat_id(db, nombre):
    return db.query(Categoria).filter_by(nombre=nombre).one().id


def leer_producto(db, nombre):
    db.expire_all()
    return producto(db, nombre)


# ---------- ver y permisos ----------


def test_carta_completa_incluye_lo_apagado(client, db, admin, carta):
    producto(db, "Lomo Clásico").visible = False
    producto(db, "Muzzarella").categoria.activa = False
    db.commit()
    r = client.get("/api/carta", headers=headers(admin))
    assert r.status_code == 200
    cats = {c["nombre"]: c for c in r.json()}
    assert cats["Pizzas"]["activa"] is False
    nombres = [p["nombre"] for p in cats["Sandwiches Ahumados"]["productos"]]
    assert "Lomo Clásico" in nombres
    animal = next(p for p in cats["Smash Burgers"]["productos"] if p["nombre"] == "Animal")
    veggie = animal["grupos"][2]["opciones"][0]
    assert veggie["disponible"] is False


def test_cocina_no_entra_a_la_carta(client, cocina, carta):
    assert client.get("/api/carta", headers=headers(cocina)).status_code == 403


def test_cantina_ve_pero_no_edita(client, db, cantina, carta):
    h = headers(cantina)
    assert client.get("/api/carta", headers=h).status_code == 200
    assert client.post("/api/carta/categorias", json={"nombre": "Bebidas"}, headers=h).status_code == 403
    pid = producto(db, "Animal").id
    assert client.patch(f"/api/carta/productos/{pid}", json={"precio": 1}, headers=h).status_code == 403
    aumento = {"aplica_a": "todo", "porcentaje": 10, "redondeo": 500}
    assert client.post("/api/carta/aumento/aplicar", json=aumento, headers=h).status_code == 403


def test_sin_login(client, carta):
    assert client.get("/api/carta").status_code == 401


# ---------- disponibilidad (también la cantina) ----------


def test_cantina_apaga_la_bondiola(client, db, cantina, carta):
    pid = producto(db, "Bondiola Ahumada").id
    r = client.patch(f"/api/carta/productos/{pid}/disponible", json={"disponible": False}, headers=headers(cantina))
    assert r.status_code == 200 and r.json()["disponible"] is False
    # En la tienda se ve apagada y no se puede pedir
    menu = client.get("/api/tienda/menu").json()
    bondiola = next(p for c in menu for p in c["productos"] if p["nombre"] == "Bondiola Ahumada")
    assert bondiola["disponible"] is False
    items = [{"producto_id": pid, "cantidad": 1}]
    r = client.post("/api/tienda/pedidos", json={
        "modo": "take_away", "nombre": "Ana", "apellido": "Gómez", "telefono": "2615550000",
        "metodo_pago": "efectivo", "items": items,
    })
    assert r.status_code == 400

    r = client.patch(f"/api/carta/productos/{pid}/disponible", json={"disponible": True}, headers=headers(cantina))
    assert r.json()["disponible"] is True


def test_cantina_prende_una_opcion(client, db, cantina, carta):
    oid = opcion(db, "Animal", "Medallón veggie").id
    r = client.patch(f"/api/carta/opciones/{oid}/disponible", json={"disponible": True}, headers=headers(cantina))
    assert r.status_code == 200 and r.json()["disponible"] is True


def test_cocina_no_cambia_disponibilidad(client, db, cocina, carta):
    pid = producto(db, "Animal").id
    r = client.patch(f"/api/carta/productos/{pid}/disponible", json={"disponible": False}, headers=headers(cocina))
    assert r.status_code == 403


def test_disponible_de_algo_que_no_existe(client, admin, carta):
    r = client.patch("/api/carta/productos/999/disponible", json={"disponible": False}, headers=headers(admin))
    assert r.status_code == 404


# ---------- ABM ----------


def test_abm_categoria(client, db, admin, carta):
    h = headers(admin)
    r = client.post("/api/carta/categorias", json={"nombre": "  Bebidas "}, headers=h)
    assert r.status_code == 201
    cat = r.json()
    assert cat["nombre"] == "Bebidas" and cat["orden"] == 4 and cat["productos"] == []

    r = client.patch(f"/api/carta/categorias/{cat['id']}", json={"activa": False}, headers=h)
    assert r.json()["activa"] is False and r.json()["nombre"] == "Bebidas"

    assert client.delete(f"/api/carta/categorias/{cat['id']}", headers=h).status_code == 204
    assert client.patch(f"/api/carta/categorias/{cat['id']}", json={"activa": True}, headers=h).status_code == 404


def test_no_se_borra_una_categoria_con_productos(client, db, admin, carta):
    r = client.delete(f"/api/carta/categorias/{cat_id(db, 'Pizzas')}", headers=headers(admin))
    assert r.status_code == 409


def test_abm_producto_completo(client, db, admin, carta):
    h = headers(admin)
    cid = cat_id(db, "Para Picar")
    r = client.post("/api/carta/productos", json={
        "categoria_id": cid, "nombre": "Nachos", "descripcion": "Con cheddar", "precio": 8000,
    }, headers=h)
    assert r.status_code == 201, r.text
    prod = r.json()
    assert prod["orden"] == 4 and prod["precio"] == 8000 and prod["grupos"] == []

    r = client.post(f"/api/carta/productos/{prod['id']}/grupos", json={
        "nombre": "Tamaño", "tipo": "unica", "obligatorio": True, "max_selecciones": 1,
    }, headers=h)
    assert r.status_code == 201
    gid = r.json()["id"]

    r = client.post(f"/api/carta/grupos/{gid}/opciones", json={"nombre": "Chico", "precio_extra": 0}, headers=h)
    assert r.status_code == 201 and r.json()["cantidad_max"] == 1
    r = client.post(f"/api/carta/grupos/{gid}/opciones", json={"nombre": "Grande", "precio_extra": 3000}, headers=h)
    grande = r.json()
    assert grande["orden"] == 1

    # Ya se puede pedir desde la tienda, con el precio que calcula el backend
    p = hacer_pedido(client, db, modo="take_away", items=[
        {"producto_id": prod["id"], "cantidad": 1, "opciones": [{"opcion_id": grande["id"]}]}
    ])
    assert p["total"] == 11000

    r = client.patch(f"/api/carta/opciones/{grande['id']}", json={"precio_extra": 3500, "cantidad_max": None}, headers=h)
    assert r.json()["precio_extra"] == 3500 and r.json()["cantidad_max"] is None

    r = client.patch(f"/api/carta/grupos/{gid}", json={"nombre": "Porción"}, headers=h)
    assert r.json()["nombre"] == "Porción" and r.json()["max_selecciones"] == 1

    r = client.patch(f"/api/carta/productos/{prod['id']}", json={"etiqueta": "Nuevo", "precio": 8500}, headers=h)
    assert r.json()["etiqueta"] == "Nuevo" and r.json()["descripcion"] == "Con cheddar"
    r = client.patch(f"/api/carta/productos/{prod['id']}", json={"etiqueta": None}, headers=h)
    assert r.json()["etiqueta"] is None

    assert client.delete(f"/api/carta/opciones/{grande['id']}", headers=h).status_code == 204
    assert client.delete(f"/api/carta/grupos/{gid}", headers=h).status_code == 204
    assert client.delete(f"/api/carta/productos/{prod['id']}", headers=h).status_code == 204
    # El pedido viejo sigue entero
    assert client.get(f"/api/tienda/pedidos/{p['codigo']}").json()["total"] == 11000


def test_mover_producto_de_categoria(client, db, admin, carta):
    pid = producto(db, "Super Pancho").id
    r = client.patch(f"/api/carta/productos/{pid}", json={"categoria_id": cat_id(db, "Pizzas")}, headers=headers(admin))
    assert r.json()["categoria_id"] == cat_id(db, "Pizzas")
    assert r.json()["orden"] == 3


def test_producto_en_categoria_que_no_existe(client, admin, carta):
    r = client.post("/api/carta/productos", json={"categoria_id": 999, "nombre": "X1", "precio": 1}, headers=headers(admin))
    assert r.status_code == 404


def test_precio_negativo_no(client, db, admin, carta):
    pid = producto(db, "Animal").id
    r = client.patch(f"/api/carta/productos/{pid}", json={"precio": -5}, headers=headers(admin))
    assert r.status_code == 422


# ---------- orden ----------


def test_reordenar_categorias(client, db, admin, carta):
    ids = [c.id for c in db.query(Categoria).order_by(Categoria.orden)]
    nuevo = list(reversed(ids))
    r = client.put("/api/carta/categorias/orden", json={"ids": nuevo}, headers=headers(admin))
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == nuevo
    menu = client.get("/api/tienda/menu").json()
    assert menu[0]["nombre"] == "Para Picar"


def test_reordenar_categorias_incompleto(client, db, admin, carta):
    ids = [c.id for c in db.query(Categoria)]
    assert client.put("/api/carta/categorias/orden", json={"ids": ids[:2]}, headers=headers(admin)).status_code == 400
    assert client.put("/api/carta/categorias/orden", json={"ids": ids + [ids[0]]}, headers=headers(admin)).status_code == 400


def test_reordenar_productos(client, db, admin, carta):
    cid = cat_id(db, "Pizzas")
    ids = [p.id for p in db.get(Categoria, cid).productos]
    nuevo = [ids[2], ids[0], ids[1]]
    r = client.put(f"/api/carta/categorias/{cid}/orden-productos", json={"ids": nuevo}, headers=headers(admin))
    assert r.status_code == 200
    assert [p["id"] for p in r.json()["productos"]] == nuevo


def test_reordenar_con_producto_de_otra_categoria(client, db, admin, carta):
    cid = cat_id(db, "Pizzas")
    ids = [p.id for p in db.get(Categoria, cid).productos]
    ids[0] = producto(db, "Animal").id
    r = client.put(f"/api/carta/categorias/{cid}/orden-productos", json={"ids": ids}, headers=headers(admin))
    assert r.status_code == 400


# ---------- aumento de precios ----------


@pytest.mark.parametrize("valor,paso,esperado", [
    (13750, 500, 14000), (14300, 500, 14500), (15950, 500, 16000), (14850, 500, 15000),
    (2750, 500, 3000), (12340, 100, 12300), (12350, 100, 12400), (12499, 1000, 12000), (12500, 1000, 13000),
])
def test_redondear(valor, paso, esperado):
    assert redondear(Decimal(valor), paso) == esperado


def aumento(client, admin, cuerpo, aplicar=False):
    ruta = "aplicar" if aplicar else "vista-previa"
    return client.post(f"/api/carta/aumento/{ruta}", json=cuerpo, headers=headers(admin))


def test_vista_previa_como_en_la_maqueta(client, db, admin, carta):
    # Smash Burgers +10 % redondeando a $500, como la parte 4 de BRUTO-pantallas.html
    r = aumento(client, admin, {"aplica_a": "categoria", "categoria_id": cat_id(db, "Smash Burgers"), "porcentaje": 10, "redondeo": 500})
    assert r.status_code == 200, r.text
    filas = {p["nombre"]: p for p in r.json()["productos"]}

    def doble(nombre):
        return next((o for o in filas[nombre]["opciones"] if o["nombre"] == "Doble"), None)

    esperado = {  # simple viejo, simple nuevo, doble viejo, doble nuevo
        "Cuarto de Libra": (12500, 14000, 14500, 16000),
        "Clásica": (12500, 14000, 14500, 16000),
        "Criolla": (13000, 14500, 14500, 16000),
        "Animal": (13500, 15000, 15000, 16500),
    }
    for nombre, (sv, sn, dv, dn) in esperado.items():
        assert (filas[nombre]["precio_viejo"], filas[nombre]["precio_nuevo"]) == (sv, sn)
        d = doble(nombre)
        assert (d["final_viejo"], d["final_nuevo"]) == (dv, dn)
        # El extra que se guarda es la diferencia con el simple nuevo
        assert d["extra_nuevo"] == dn - sn

    assert filas["Big Pollo"]["precio_nuevo"] == 14000 and doble("Big Pollo") is None
    extra = next(o for o in filas["Animal"]["opciones"] if o["nombre"] == "Extra carne y queso")
    assert (extra["extra_viejo"], extra["extra_nuevo"]) == (2500, 3000)
    # El Simple ($0) y la veggie ($0) no aparecen
    assert {o["nombre"] for o in filas["Animal"]["opciones"]} == {"Doble", "Extra carne y queso"}
    # 5 burgers + 4 dobles + 5 extra carne (uno por burger)
    assert r.json()["cantidad_precios"] == 14


def test_vista_previa_no_guarda_nada(client, db, admin, carta):
    aumento(client, admin, {"aplica_a": "todo", "porcentaje": 50, "redondeo": 100})
    assert leer_producto(db, "Animal").precio == 13500
    assert opcion(db, "Animal", "Doble").precio_extra == 1500


def test_aplicar_aumento(client, db, admin, carta):
    cuerpo = {"aplica_a": "categoria", "categoria_id": cat_id(db, "Smash Burgers"), "porcentaje": 10, "redondeo": 500}
    previa = aumento(client, admin, cuerpo).json()
    r = aumento(client, admin, cuerpo, aplicar=True)
    assert r.status_code == 200
    assert r.json() == previa  # lo que se vio es lo que se guardó

    assert leer_producto(db, "Animal").precio == 15000
    assert opcion(db, "Animal", "Doble").precio_extra == 1500
    assert opcion(db, "Cuarto de Libra", "Doble").precio_extra == 2000
    assert opcion(db, "Animal", "Extra carne y queso").precio_extra == 3000
    assert leer_producto(db, "Muzzarella").precio == 14000  # otra categoría, no se toca

    # Y la tienda cobra el precio nuevo: 16.500 el doble + 3.000 el extra
    p = hacer_pedido(client, db, items=[{
        "producto_id": producto(db, "Animal").id, "cantidad": 1,
        "opciones": [{"opcion_id": opcion(db, "Animal", "Doble").id},
                     {"opcion_id": opcion(db, "Animal", "Extra carne y queso").id}],
    }])
    assert p["total"] == 19500


def test_aumento_no_toca_pedidos_hechos(client, db, admin, carta):
    viejo = hacer_pedido(client, db)
    aumento(client, admin, {"aplica_a": "todo", "porcentaje": 20, "redondeo": 1000}, aplicar=True)
    r = client.get(f"/api/tienda/pedidos/{viejo['codigo']}").json()
    assert r["total"] == 20000
    assert r["items"][0]["precio_unitario"] == 20000


def test_aumento_a_una_lista_de_productos(client, db, admin, carta):
    ids = [producto(db, "Papas Fritas").id, producto(db, "Super Pancho").id]
    r = aumento(client, admin, {"aplica_a": "productos", "producto_ids": ids, "porcentaje": 10, "redondeo": 100}, aplicar=True)
    assert [p["nombre"] for p in r.json()["productos"]] == ["Papas Fritas", "Super Pancho"]
    assert leer_producto(db, "Papas Fritas").precio == 9900
    assert leer_producto(db, "Super Pancho").precio == 4400
    assert leer_producto(db, "Animal").precio == 13500


def test_aumento_todo(client, db, admin, carta):
    r = aumento(client, admin, {"aplica_a": "todo", "porcentaje": 10, "redondeo": 1000})
    assert len(r.json()["productos"]) == db.query(Producto).count()


def test_bajar_precios(client, db, admin, carta):
    r = aumento(client, admin, {"aplica_a": "productos", "producto_ids": [producto(db, "Papas Fritas").id], "porcentaje": -10, "redondeo": 500})
    assert r.json()["productos"][0]["precio_nuevo"] == 8000  # 8.100 -> 8.000


def test_doble_nunca_queda_mas_barato_que_el_simple(client, db, admin, carta):
    # Un doble con extra chiquito: al redondear no puede quedar en negativo
    op = opcion(db, "Criolla", "Doble")
    op.precio_extra = 100
    db.commit()
    r = aumento(client, admin, {"aplica_a": "productos", "producto_ids": [producto(db, "Criolla").id], "porcentaje": 7, "redondeo": 1000})
    doble = next(o for o in r.json()["productos"][0]["opciones"] if o["nombre"] == "Doble")
    assert doble["extra_nuevo"] >= 0


@pytest.mark.parametrize("cuerpo,codigo", [
    ({"aplica_a": "categoria", "porcentaje": 10}, 422),
    ({"aplica_a": "productos", "producto_ids": [], "porcentaje": 10}, 422),
    ({"aplica_a": "todo", "porcentaje": 10, "redondeo": 250}, 422),
    ({"aplica_a": "todo", "porcentaje": 500}, 422),
    ({"aplica_a": "categoria", "categoria_id": 999, "porcentaje": 10}, 404),
    ({"aplica_a": "productos", "producto_ids": [999], "porcentaje": 10}, 404),
])
def test_aumento_mal_armado(client, admin, carta, cuerpo, codigo):
    assert aumento(client, admin, cuerpo).status_code == codigo


# ---------- aviso al panel ----------


def test_cambio_de_carta_avisa_al_panel(client, db, admin, cantina, carta):
    pid = producto(db, "Animal").id
    with ws_panel(client, cantina) as ws:
        client.patch(f"/api/carta/productos/{pid}/disponible", json={"disponible": False}, headers=headers(cantina))
        assert ws.receive_json() == {"evento": "carta_actualizada"}
        aumento(client, admin, {"aplica_a": "todo", "porcentaje": 5, "redondeo": 100}, aplicar=True)
        assert ws.receive_json() == {"evento": "carta_actualizada"}
        client.post("/api/carta/categorias", json={"nombre": "Bebidas"}, headers=headers(admin))
        assert ws.receive_json() == {"evento": "carta_actualizada"}


def test_vista_previa_no_avisa(client, db, admin, cantina, carta):
    with ws_panel(client, cantina) as ws:
        aumento(client, admin, {"aplica_a": "todo", "porcentaje": 5, "redondeo": 100})
        client.post("/api/carta/categorias", json={"nombre": "Bebidas"}, headers=headers(admin))
        # Lo primero que llega es lo de la categoría, la vista previa no mandó nada
        assert ws.receive_json() == {"evento": "carta_actualizada"}
        ws.send_text("ping")
        assert ws.receive_text() == "pong"
    assert db.query(Opcion).count() > 0
