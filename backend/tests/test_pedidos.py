import pytest

from tests.conftest import datos_pedido, hacer_pedido, opcion, producto


def item(db, nombre, cantidad=1, opciones=(), nota=None):
    return {
        "producto_id": producto(db, nombre).id,
        "cantidad": cantidad,
        "nota": nota,
        "opciones": [
            {"opcion_id": opcion(db, nombre, o).id, "cantidad": c} for o, c in opciones
        ],
    }


# ---------- precio ----------


def test_precio_doble_con_extras(client, db, carta):
    # Animal 13.500 + doble 1.500 + 2 x extra carne 2.500 = 20.000
    p = hacer_pedido(client, db)
    assert p["total"] == 20000
    assert p["items"][0]["precio_unitario"] == 20000
    opciones = {o["nombre_opcion"]: o for o in p["items"][0]["opciones"]}
    assert opciones["Extra carne y queso"]["cantidad"] == 2
    assert opciones["Doble"]["precio_extra"] == 1500


def test_precio_con_cantidades_y_varios_items(client, db, carta):
    items = [
        item(db, "Clásica", cantidad=2, opciones=[("Simple", 1)]),
        item(db, "Papas Fritas", cantidad=3),
    ]
    p = hacer_pedido(client, db, items=items)
    # 2 x 12.500 + 3 x 9.000
    assert p["total"] == 52000


def test_el_precio_que_manda_el_celu_se_ignora(client, db, carta):
    datos = datos_pedido(db, total=1, items=[item(db, "Papas Fritas") | {"precio": 1}])
    r = client.post("/api/tienda/pedidos", json=datos)
    assert r.status_code == 201
    assert r.json()["total"] == 9000


def test_nota_del_item_y_del_pedido(client, db, carta):
    p = hacer_pedido(
        client, db, items=[item(db, "Super Pancho", nota="  sin papas  ")], notas="  apurado "
    )
    assert p["items"][0]["nota"] == "sin papas"
    assert p["notas"] == "apurado"


# ---------- estado según el pago ----------


def test_efectivo_entra_recibido(client, db, carta):
    p = hacer_pedido(client, db, metodo_pago="efectivo")
    assert p["estado"] == "recibido"
    assert p["estado_pago"] == "pendiente"
    assert len(p["codigo"]) == 32


def test_mercadopago_queda_esperando_pago(client, db, carta):
    p = hacer_pedido(client, db, metodo_pago="mercadopago")
    assert p["estado"] == "pendiente_pago"


# ---------- validaciones de opciones ----------


def mandar(client, db, items):
    return client.post("/api/tienda/pedidos", json=datos_pedido(db, items=items))


def test_falta_grupo_obligatorio(client, db, carta):
    r = mandar(client, db, [item(db, "Animal")])
    assert r.status_code == 400
    assert r.json()["detail"] == "Elegí tamaño para Animal"


def test_grupo_unica_con_dos_opciones(client, db, carta):
    r = mandar(client, db, [item(db, "Animal", opciones=[("Simple", 1), ("Doble", 1)])])
    assert r.status_code == 400
    assert "una sola opción" in r.json()["detail"]


def test_opcion_de_otro_producto(client, db, carta):
    it = item(db, "Animal", opciones=[("Simple", 1)])
    it["opciones"].append({"opcion_id": opcion(db, "Clásica", "Doble").id})
    r = mandar(client, db, [it])
    assert r.status_code == 400
    assert "no corresponde" in r.json()["detail"]


def test_opcion_repetida(client, db, carta):
    r = mandar(client, db, [item(db, "Animal", opciones=[("Simple", 1), ("Simple", 1)])])
    assert r.status_code == 400
    assert "repetida" in r.json()["detail"]


def test_opcion_apagada(client, db, carta):
    r = mandar(client, db, [item(db, "Animal", opciones=[("Simple", 1), ("Medallón veggie", 1)])])
    assert r.status_code == 400
    assert r.json()["detail"] == "Medallón veggie no está disponible ahora"


def test_opcion_mas_veces_que_su_tope(client, db, carta):
    r = mandar(client, db, [item(db, "Animal", opciones=[("Doble", 2)])])
    assert r.status_code == 400
    assert r.json()["detail"] == "Doble se puede pedir una vez"


def test_extra_sin_tope_acepta_muchas(client, db, carta):
    r = mandar(client, db, [item(db, "Animal", opciones=[("Simple", 1), ("Extra carne y queso", 5)])])
    assert r.status_code == 201
    assert r.json()["total"] == 13500 + 5 * 2500


def test_max_selecciones(client, db, carta):
    g = producto(db, "Animal").grupos[1]
    g.max_selecciones = 0
    db.commit()
    r = mandar(client, db, [item(db, "Animal", opciones=[("Simple", 1), ("Extra carne y queso", 1)])])
    assert r.status_code == 400
    assert "hasta 0" in r.json()["detail"]


def test_producto_no_disponible(client, db, carta):
    r = mandar(client, db, [item(db, "Pepperoni")])
    assert r.status_code == 400
    assert r.json()["detail"] == "Pepperoni no está disponible ahora"


def test_producto_no_visible(client, db, carta):
    producto(db, "Lomo Clásico").visible = False
    db.commit()
    r = mandar(client, db, [item(db, "Lomo Clásico")])
    assert r.status_code == 400


def test_producto_que_no_existe(client, db, carta):
    r = mandar(client, db, [{"producto_id": 9999, "cantidad": 1}])
    assert r.status_code == 400
    assert "ya no está en la carta" in r.json()["detail"]


# ---------- validaciones de datos del cliente ----------


def test_comer_adentro_sin_ubicacion(client, db, carta):
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db, ubicacion="  "))
    assert r.status_code == 422
    assert "dónde estás" in r.text


def test_take_away_no_guarda_ubicacion(client, db, carta):
    p = hacer_pedido(client, db, modo="take_away", ubicacion="cancha 1")
    assert p["ubicacion"] is None


def test_ubicacion_se_limpia(client, db, carta):
    p = hacer_pedido(client, db, ubicacion="  frente   a la  cancha 3 ")
    assert p["ubicacion"] == "frente a la cancha 3"


@pytest.mark.parametrize("telefono", ["123", "abc", "1" * 20])
def test_telefono_invalido(client, db, carta, telefono):
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db, telefono=telefono))
    assert r.status_code == 422


def test_telefono_se_guarda_solo_numeros(client, db, carta):
    from app.models import Pedido

    p = hacer_pedido(client, db, telefono="+54 9 261 555-0142")
    guardado = db.query(Pedido).filter_by(codigo=p["codigo"]).one()
    assert guardado.telefono == "5492615550142"


def test_pedido_sin_items(client, db, carta):
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db, items=[]))
    assert r.status_code == 422


def test_nombre_muy_corto(client, db, carta):
    r = client.post("/api/tienda/pedidos", json=datos_pedido(db, nombre=" J "))
    assert r.status_code == 422


# ---------- seguimiento ----------


def test_ver_pedido_por_codigo(client, db, carta):
    p = hacer_pedido(client, db)
    r = client.get(f"/api/tienda/pedidos/{p['codigo']}")
    assert r.status_code == 200
    assert r.json()["numero"] == p["numero"]
    # El cliente no ve el teléfono ni el id
    assert "telefono" not in r.json() and "id" not in r.json()


def test_ver_pedido_que_no_existe(client, carta):
    assert client.get("/api/tienda/pedidos/noexiste").status_code == 404


def test_pedido_viejo_no_cambia_si_cambia_el_precio(client, db, carta):
    p = hacer_pedido(client, db, items=[item(db, "Papas Fritas")])
    producto(db, "Papas Fritas").precio = 99999
    db.commit()
    r = client.get(f"/api/tienda/pedidos/{p['codigo']}")
    assert r.json()["total"] == 9000
