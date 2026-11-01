from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import (
    EstadoPedido,
    GrupoOpciones,
    MetodoPago,
    Opcion,
    Pedido,
    PedidoItem,
    PedidoItemOpcion,
    Producto,
    TipoGrupo,
)
from app.schemas.pedido import ItemNuevo, PedidoNuevo


class PedidoInvalido(Exception):
    """Algo del pedido no cierra (producto apagado, opción que no va, etc.).
    El mensaje es para mostrárselo al cliente tal cual."""


# ---------- numeración del día ----------


def inicio_jornada(ahora: datetime | None = None) -> datetime:
    # La jornada va de las 6 de la mañana a las 6 del día siguiente
    zona = ZoneInfo(settings.zona_horaria)
    ahora = (ahora or datetime.now(zona)).astimezone(zona)
    corte = datetime.combine(ahora.date(), time(settings.hora_corte_jornada), tzinfo=zona)
    if ahora < corte:
        corte -= timedelta(days=1)
    return corte


def siguiente_numero(db: Session) -> int:
    # Si entran dos pedidos en el mismo segundo, este lock hace que uno espere
    # al otro y no salgan los dos con el mismo número. Se suelta solo al commitear
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(4242)"))

    ultimo = db.scalar(
        select(func.max(Pedido.numero)).where(Pedido.created_at >= inicio_jornada())
    )
    return (ultimo or 0) + 1


# ---------- armado y precio de cada item ----------


def armar_item(producto: Producto, item: ItemNuevo) -> PedidoItem:
    if not producto.visible or not producto.disponible:
        raise PedidoInvalido(f"{producto.nombre} no está disponible ahora")

    # Todas las opciones que puede tener este producto, por id
    opciones_validas: dict[int, Opcion] = {
        op.id: op for grupo in producto.grupos for op in grupo.opciones
    }

    elegidas_por_grupo: dict[int, list[tuple[Opcion, int]]] = defaultdict(list)
    ya_vistas = set()

    for elegida in item.opciones:
        opcion = opciones_validas.get(elegida.opcion_id)
        if opcion is None:
            raise PedidoInvalido(f"Hay una opción que no corresponde a {producto.nombre}")
        if opcion.id in ya_vistas:
            raise PedidoInvalido(f"La opción {opcion.nombre} está repetida")
        if not opcion.disponible:
            raise PedidoInvalido(f"{opcion.nombre} no está disponible ahora")
        if opcion.cantidad_max is not None and elegida.cantidad > opcion.cantidad_max:
            veces = "una vez" if opcion.cantidad_max == 1 else f"{opcion.cantidad_max} veces"
            raise PedidoInvalido(f"{opcion.nombre} se puede pedir {veces}")
        ya_vistas.add(opcion.id)
        elegidas_por_grupo[opcion.grupo_id].append((opcion, elegida.cantidad))

    # Reglas de cada grupo: obligatorio, única, tope de selecciones
    for grupo in producto.grupos:
        elegidas = elegidas_por_grupo.get(grupo.id, [])

        if grupo.obligatorio and not elegidas:
            raise PedidoInvalido(f"Elegí {grupo.nombre.lower()} para {producto.nombre}")

        if grupo.tipo == TipoGrupo.unica and (
            len(elegidas) > 1 or any(cant > 1 for _, cant in elegidas)
        ):
            raise PedidoInvalido(f"En {grupo.nombre.lower()} se elige una sola opción")

        if grupo.max_selecciones is not None and len(elegidas) > grupo.max_selecciones:
            raise PedidoInvalido(
                f"En {grupo.nombre.lower()} podés elegir hasta {grupo.max_selecciones}"
            )

    # El precio lo calculamos acá, nunca confiamos en lo que manda el celu
    precio_unitario = Decimal(producto.precio)
    opciones_item = []

    for grupo in producto.grupos:
        for opcion, cantidad in elegidas_por_grupo.get(grupo.id, []):
            precio_unitario += Decimal(opcion.precio_extra) * cantidad
            opciones_item.append(
                PedidoItemOpcion(
                    nombre_grupo=grupo.nombre,
                    nombre_opcion=opcion.nombre,
                    precio_extra=opcion.precio_extra,
                    cantidad=cantidad,
                )
            )

    return PedidoItem(
        producto_id=producto.id,
        nombre_producto=producto.nombre,
        precio_unitario=precio_unitario,
        cantidad=item.cantidad,
        nota=item.nota,
        opciones=opciones_item,
    )


# ---------- crear el pedido ----------


def crear_pedido(db: Session, datos: PedidoNuevo) -> Pedido:
    ids = {item.producto_id for item in datos.items}
    productos = {
        p.id: p
        for p in db.scalars(
            select(Producto)
            .where(Producto.id.in_(ids))
            .options(selectinload(Producto.grupos).selectinload(GrupoOpciones.opciones))
        )
    }

    faltantes = ids - productos.keys()
    if faltantes:
        raise PedidoInvalido("Hay un producto en tu pedido que ya no está en la carta")

    items = [armar_item(productos[item.producto_id], item) for item in datos.items]
    total = sum((it.precio_unitario * it.cantidad for it in items), Decimal(0))

    # Efectivo: entra directo a la cantina y se cobra al entregar.
    # Mercado Pago: queda esperando hasta que MP confirme el pago (webhook)
    if datos.metodo_pago == MetodoPago.efectivo:
        estado = EstadoPedido.recibido
    else:
        estado = EstadoPedido.pendiente_pago

    pedido = Pedido(
        numero=siguiente_numero(db),
        modo=datos.modo,
        ubicacion=datos.ubicacion,
        nombre=datos.nombre,
        apellido=datos.apellido,
        telefono=datos.telefono,
        notas=(datos.notas or "").strip() or None,
        metodo_pago=datos.metodo_pago,
        estado=estado,
        total=total,
        items=items,
    )

    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return pedido


def buscar_por_codigo(db: Session, codigo: str) -> Pedido | None:
    return db.scalar(
        select(Pedido)
        .where(Pedido.codigo == codigo)
        .options(selectinload(Pedido.items).selectinload(PedidoItem.opciones))
    )
