"""Manejo de la carta desde el panel: ABM, orden, disponibilidad y aumentos."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Categoria, GrupoOpciones, Opcion, Producto, TipoGrupo
from app.schemas.carta import AumentoPrecios


class CartaInvalida(Exception):
    """Algo no cierra (id que no existe, orden incompleto...). Va como 400."""


class NoExiste(CartaInvalida):
    """Va como 404."""


def carta_completa(db: Session) -> list[Categoria]:
    return list(
        db.scalars(
            select(Categoria)
            .order_by(Categoria.orden, Categoria.id)
            .options(
                selectinload(Categoria.productos)
                .selectinload(Producto.grupos)
                .selectinload(GrupoOpciones.opciones)
            )
        )
    )


def traer(db: Session, modelo, id_: int, nombre: str):
    obj = db.get(modelo, id_)
    if obj is None:
        raise NoExiste(f"No existe ese {nombre}")
    return obj


def siguiente_orden(db: Session, columna, *filtros) -> int:
    # Lo nuevo va al final de la lista
    ultimo = db.scalar(select(func.max(columna)).where(*filtros))
    return 0 if ultimo is None else ultimo + 1


def aplicar_cambios(obj, cambios, campos_con_null=()):
    # Solo lo que vino en el JSON. Los campos donde null significa algo
    # ("sin tope") se pisan aunque vengan en null
    for campo in cambios.model_fields_set:
        valor = getattr(cambios, campo)
        if valor is None and campo not in campos_con_null:
            continue
        if isinstance(valor, str):
            valor = valor.strip() or None
        setattr(obj, campo, valor)


def reordenar(objetos: list, ids: list[int]):
    actuales = {o.id: o for o in objetos}
    if len(ids) != len(set(ids)) or set(ids) != set(actuales):
        raise CartaInvalida("Mandá todos los ids, sin repetir ni agregar otros")
    for posicion, id_ in enumerate(ids):
        actuales[id_].orden = posicion


# ---------- aumento de precios ----------


def redondear(valor: Decimal, a: int) -> Decimal:
    # Al múltiplo más cercano: 13.750 con redondeo 500 da 14.000
    paso = Decimal(a)
    return (Decimal(valor) / paso).quantize(Decimal(1), rounding=ROUND_HALF_UP) * paso


def productos_alcanzados(db: Session, datos: AumentoPrecios) -> list[Producto]:
    consulta = (
        select(Producto)
        .join(Categoria)
        .order_by(Categoria.orden, Producto.orden, Producto.id)
        .options(
            selectinload(Producto.categoria),
            selectinload(Producto.grupos).selectinload(GrupoOpciones.opciones),
        )
    )
    if datos.aplica_a == "categoria":
        traer(db, Categoria, datos.categoria_id, "categoría")
        consulta = consulta.where(Producto.categoria_id == datos.categoria_id)
    elif datos.aplica_a == "productos":
        consulta = consulta.where(Producto.id.in_(datos.producto_ids))
    productos = list(db.scalars(consulta))
    if datos.aplica_a == "productos" and len(productos) != len(set(datos.producto_ids)):
        raise NoExiste("Hay un producto en la lista que no existe")
    return productos


def calcular_aumento(db: Session, datos: AumentoPrecios) -> dict:
    """Calcula los precios nuevos SIN guardar nada (para la vista previa).

    Lo de "Doble": el precio del doble es un extra sobre el simple. Si le
    aplico el % al extra solo, el doble final queda con números feos.
    Entonces en los grupos de opción única (Simple/Doble) redondeo el precio
    final que ve el cliente (simple + extra) y el extra nuevo sale de restar.
    En los agregados (grupos múltiples) el extra es un precio en sí: lo redondeo directo.
    """
    factor = 1 + datos.porcentaje / 100
    resultado = []
    cantidad = 0

    for producto in productos_alcanzados(db, datos):
        base_vieja = Decimal(producto.precio)
        base_nueva = max(redondear(base_vieja * factor, datos.redondeo), Decimal(0))
        cantidad += 1
        opciones = []

        for grupo in producto.grupos:
            for op in grupo.opciones:
                extra_viejo = Decimal(op.precio_extra)
                if extra_viejo <= 0:
                    continue  # el "Simple" y las opciones gratis no cambian
                if grupo.tipo == TipoGrupo.unica:
                    final_viejo = base_vieja + extra_viejo
                    final_nuevo = redondear(final_viejo * factor, datos.redondeo)
                    extra_nuevo = max(final_nuevo - base_nueva, Decimal(0))
                    final_nuevo = base_nueva + extra_nuevo
                else:
                    final_viejo = extra_viejo
                    extra_nuevo = redondear(extra_viejo * factor, datos.redondeo)
                    final_nuevo = extra_nuevo
                cantidad += 1
                opciones.append(
                    {
                        "opcion_id": op.id,
                        "grupo": grupo.nombre,
                        "nombre": op.nombre,
                        "extra_viejo": extra_viejo,
                        "extra_nuevo": extra_nuevo,
                        "final_viejo": final_viejo,
                        "final_nuevo": final_nuevo,
                    }
                )

        resultado.append(
            {
                "producto_id": producto.id,
                "nombre": producto.nombre,
                "categoria": producto.categoria.nombre,
                "precio_viejo": base_vieja,
                "precio_nuevo": base_nueva,
                "opciones": opciones,
            }
        )

    return {"productos": resultado, "cantidad_precios": cantidad}


def aplicar_aumento(db: Session, datos: AumentoPrecios) -> dict:
    # Mismo cálculo que la vista previa, así lo que ve Renzo es lo que se guarda.
    # Los pedidos ya hechos no cambian: tienen el precio copiado
    calculo = calcular_aumento(db, datos)
    for p in calculo["productos"]:
        db.get(Producto, p["producto_id"]).precio = p["precio_nuevo"]
        for o in p["opciones"]:
            db.get(Opcion, o["opcion_id"]).precio_extra = o["extra_nuevo"]
    db.commit()
    return calculo
