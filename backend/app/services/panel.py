from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EstadoPago, EstadoPedido, MetodoPago, Pedido, PedidoItem, Rol, Usuario
from app.services.pedidos import PedidoInvalido, inicio_jornada

E = EstadoPedido

# Para dónde puede ir cada estado. Todo lo que no esté acá se rechaza,
# así nadie pasa un pedido de "entregado" a "recibido" por error
TRANSICIONES = {
    E.pendiente_pago: {E.cancelado},  # lo mueve el webhook de MP, a mano solo se cancela
    E.recibido: {E.en_preparacion, E.cancelado},
    E.en_preparacion: {E.listo, E.recibido, E.cancelado},  # recibido = "lo mandé sin querer"
    E.listo: {E.entregado, E.en_preparacion, E.cancelado},
    E.entregado: set(),
    E.cancelado: set(),
}

# La cocina solo mueve lo de la cocina. Cancelar y entregar es cosa de la cantina
PERMITIDO_COCINA = {
    (E.recibido, E.en_preparacion),
    (E.en_preparacion, E.listo),
    (E.listo, E.en_preparacion),
}

ACTIVOS = [E.recibido, E.en_preparacion, E.listo]

# Para los mensajes de error, que no le aparezca "pendiente_pago" al de la cantina
NOMBRES = {
    E.pendiente_pago: "esperando el pago",
    E.recibido: "recibido",
    E.en_preparacion: "en preparación",
    E.listo: "listo",
    E.entregado: "entregado",
    E.cancelado: "cancelado",
}


AVISO_DEVOLVER_MP = "Acordate de devolver el pago desde Mercado Pago"


class SinPermiso(PedidoInvalido):
    """El usuario no puede hacer esto por su rol (va como 403)."""


def _con_items():
    return selectinload(Pedido.items).selectinload(PedidoItem.opciones)


def pedidos_de_la_jornada(
    db: Session,
    estados: list[EstadoPedido] | None = None,
    sin_pendientes_de_pago: bool = False,
) -> list[Pedido]:
    consulta = (
        select(Pedido)
        .where(Pedido.created_at >= inicio_jornada())
        .options(_con_items())
        .order_by(Pedido.numero)
    )
    if estados:
        consulta = consulta.where(Pedido.estado.in_(estados))
    if sin_pendientes_de_pago:
        # La cocina no tiene que ver lo que todavía no se pagó
        consulta = consulta.where(Pedido.estado != E.pendiente_pago)
    return list(db.scalars(consulta))


def es_mp_pagado(pedido: Pedido) -> bool:
    return pedido.metodo_pago == MetodoPago.mercadopago and pedido.estado_pago == EstadoPago.aprobado


def buscar(db: Session, pedido_id: int) -> Pedido | None:
    return db.scalar(select(Pedido).where(Pedido.id == pedido_id).options(_con_items()))


def cambiar_estado(db: Session, pedido: Pedido, nuevo: EstadoPedido, usuario: Usuario) -> Pedido:
    actual = pedido.estado
    if nuevo == actual:
        return pedido

    if nuevo not in TRANSICIONES[actual]:
        raise PedidoInvalido(f"Un pedido {NOMBRES[actual]} no puede pasar a {NOMBRES[nuevo]}")

    if usuario.rol == Rol.cocina and (actual, nuevo) not in PERMITIDO_COCINA:
        raise PedidoInvalido("Desde la cocina solo se puede marcar en preparación o listo")

    if (
        nuevo == E.entregado
        and pedido.metodo_pago == MetodoPago.efectivo
        and pedido.estado_pago != EstadoPago.aprobado
    ):
        raise PedidoInvalido("Cobralo antes de marcarlo entregado")

    # Si ya se pagó por MP, cancelar implica devolver la plata: eso lo decide Renzo
    if nuevo == E.cancelado and es_mp_pagado(pedido) and usuario.rol != Rol.admin:
        raise SinPermiso("Solo el admin puede cancelar un pedido ya pagado por Mercado Pago")

    pedido.estado = nuevo
    db.commit()
    return buscar(db, pedido.id)


def _validar_cobro(pedido: Pedido):
    if pedido.metodo_pago != MetodoPago.efectivo:
        raise PedidoInvalido("Este pedido se paga por Mercado Pago, no se cobra en mano")
    if pedido.estado == E.cancelado:
        raise PedidoInvalido("El pedido está cancelado")


def cobrar_efectivo(db: Session, pedido: Pedido) -> Pedido:
    _validar_cobro(pedido)
    if pedido.estado_pago == EstadoPago.aprobado:
        raise PedidoInvalido("Este pedido ya estaba cobrado")

    pedido.estado_pago = EstadoPago.aprobado
    db.commit()
    return buscar(db, pedido.id)


def cobrar_y_entregar(db: Session, pedido: Pedido, usuario: Usuario) -> Pedido:
    # El botón del chico de la cantina: cobra y entrega en una. Si ya estaba
    # cobrado, solo entrega. Valido todo antes de tocar nada
    _validar_cobro(pedido)
    if E.entregado not in TRANSICIONES[pedido.estado]:
        raise PedidoInvalido(f"Un pedido {NOMBRES[pedido.estado]} no puede pasar a entregado")

    pedido.estado_pago = EstadoPago.aprobado
    pedido.estado = E.entregado
    db.commit()
    return buscar(db, pedido.id)


def pedir_reimpresion(db: Session, pedido: Pedido) -> Pedido:
    # El agente de la ticketera imprime todo lo que tenga impreso_at vacío,
    # así que para reimprimir alcanza con vaciarlo
    if pedido.estado in (E.pendiente_pago, E.cancelado):
        raise PedidoInvalido("Este pedido no tiene comanda para imprimir")
    pedido.impreso_at = None
    db.commit()
    return buscar(db, pedido.id)


def pendientes_de_imprimir(db: Session) -> list[Pedido]:
    # Lo que la ticketera todavía no sacó: de la jornada, en cocina y sin impreso_at
    return list(
        db.scalars(
            select(Pedido)
            .where(
                Pedido.created_at >= inicio_jornada(),
                Pedido.estado.in_([E.recibido, E.en_preparacion]),
                Pedido.impreso_at.is_(None),
            )
            .options(_con_items())
            .order_by(Pedido.numero)
        )
    )


def marcar_impreso(db: Session, pedido: Pedido) -> Pedido:
    pedido.impreso_at = datetime.now(timezone.utc)
    db.commit()
    return buscar(db, pedido.id)


def resumen(db: Session) -> dict:
    pedidos = db.scalars(select(Pedido).where(Pedido.created_at >= inicio_jornada())).all()

    validos = [p for p in pedidos if p.estado not in (E.cancelado, E.pendiente_pago)]

    vendido = sum((p.total for p in validos if p.estado_pago == EstadoPago.aprobado), Decimal(0))
    a_cobrar = sum(
        (
            p.total
            for p in validos
            if p.metodo_pago == MetodoPago.efectivo and p.estado_pago != EstadoPago.aprobado
        ),
        Decimal(0),
    )

    return {
        "pedidos": len(validos),
        "vendido": vendido,
        "efectivo_a_cobrar": a_cobrar,
        "esperando_pago_mp": sum(1 for p in pedidos if p.estado == E.pendiente_pago),
    }
