"""
Caja del día: cuánto se vendió en una jornada y el historial por día.

La jornada va de las 6 de la mañana a las 6 del día siguiente (la cantina
cierra pasada la medianoche), igual que la numeración de los pedidos.
La "fecha" de una jornada es el día en que arrancó: el pedido del viernes
a la 1:30 de la madrugada es de la caja del jueves.

Qué cuenta (decidido para la tarea 3, ver DECISIONES.md):
- Pedidos válidos: los que llegaron a la cocina, o sea todo menos cancelados
  y los de Mercado Pago que todavía no se pagaron.
- Vendido = lo cobrado de los válidos: MP aprobado + efectivo ya cobrado.
- Efectivo a cobrar = efectivo de los válidos que todavía no se cobró.
- Ticket promedio = total de los pedidos válidos (cobrados o no) / cantidad.
- Cancelados = los cancelados que habían entrado a la cocina. Los de MP que
  nadie pagó (los cancela solo la tarea de fondo) van aparte en mp_sin_pagar.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import EstadoPago, EstadoPedido, MetodoPago, ModoPedido, Pedido

E = EstadoPedido
TOP_PRODUCTOS = 10
MAX_DIAS_HISTORIAL = 366


def zona() -> ZoneInfo:
    return ZoneInfo(settings.zona_horaria)


def ahora() -> datetime:
    # Aparte para poder moverla en los tests
    return datetime.now(zona())


def local(momento: datetime) -> datetime:
    # Con SQLite las fechas vuelven sin zona: están en UTC
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(zona())


def fecha_de_jornada(momento: datetime) -> date:
    return (local(momento) - timedelta(hours=settings.hora_corte_jornada)).date()


def hoy() -> date:
    return fecha_de_jornada(ahora())


def rango(desde: date, hasta: date | None = None) -> tuple[datetime, datetime]:
    """De las 6 AM de `desde` a las 6 AM del día siguiente a `hasta`, en UTC
    (en UTC para que SQLite, que compara como texto, no se corra 3 horas)."""
    hasta = hasta or desde
    corte = time(settings.hora_corte_jornada)
    inicio = datetime.combine(desde, corte, tzinfo=zona())
    fin = datetime.combine(hasta + timedelta(days=1), corte, tzinfo=zona())
    return inicio.astimezone(timezone.utc), fin.astimezone(timezone.utc)


def _pedidos(db: Session, inicio: datetime, fin: datetime, con_items: bool = False) -> list[Pedido]:
    consulta = select(Pedido).where(Pedido.created_at >= inicio, Pedido.created_at < fin).order_by(Pedido.id)
    if con_items:
        consulta = consulta.options(selectinload(Pedido.items))
    return list(db.scalars(consulta))


def es_valido(p: Pedido) -> bool:
    return p.estado not in (E.cancelado, E.pendiente_pago)


def es_mp_sin_pagar(p: Pedido) -> bool:
    return p.metodo_pago == MetodoPago.mercadopago and p.estado_pago != EstadoPago.aprobado


def _cobrado(p: Pedido) -> bool:
    return p.estado_pago == EstadoPago.aprobado


def _sumar(pedidos) -> Decimal:
    return sum((Decimal(p.total) for p in pedidos), Decimal(0))


def _numeros(pedidos: list[Pedido]) -> dict:
    """Lo que se repite en la caja del día y en cada fila del historial."""
    validos = [p for p in pedidos if es_valido(p)]
    mp = _sumar(p for p in validos if p.metodo_pago == MetodoPago.mercadopago and _cobrado(p))
    efectivo = _sumar(p for p in validos if p.metodo_pago == MetodoPago.efectivo and _cobrado(p))
    cancelados = [p for p in pedidos if p.estado == E.cancelado]
    return {
        "pedidos": len(validos),
        "vendido": mp + efectivo,
        "mercadopago": mp,
        "efectivo_cobrado": efectivo,
        "efectivo_a_cobrar": _sumar(p for p in validos if p.metodo_pago == MetodoPago.efectivo and not _cobrado(p)),
        "cancelados": sum(1 for p in cancelados if not es_mp_sin_pagar(p)),
        "mp_sin_pagar": sum(1 for p in cancelados if es_mp_sin_pagar(p)),
        "_validos": validos,
    }


def caja_del_dia(db: Session, fecha: date) -> dict:
    inicio, fin = rango(fecha)
    pedidos = _pedidos(db, inicio, fin, con_items=True)
    n = _numeros(pedidos)
    validos = n.pop("_validos")

    total_validos = _sumar(validos)
    promedio = (total_validos / len(validos)).quantize(Decimal("0.01"), ROUND_HALF_UP) if validos else Decimal(0)

    por_modo = []
    for modo in ModoPedido:
        del_modo = [p for p in validos if p.modo == modo]
        por_modo.append({"modo": modo, "pedidos": len(del_modo), "total": _sumar(del_modo)})

    # Productos: por el nombre copiado en el pedido (así cuentan aunque después se borren)
    productos: dict[str, dict] = defaultdict(lambda: {"cantidad": 0, "total": Decimal(0)})
    for p in validos:
        for it in p.items:
            fila = productos[it.nombre_producto]
            fila["cantidad"] += it.cantidad
            fila["total"] += Decimal(it.precio_unitario) * it.cantidad
    top = sorted(
        ({"nombre": nombre, **datos} for nombre, datos in productos.items()),
        key=lambda x: (-x["cantidad"], -x["total"], x["nombre"]),
    )[:TOP_PRODUCTOS]

    # Ventas por hora (hora de Mendoza), en el orden de la jornada: 6, 7... 23, 0... 5
    horas: dict[int, dict] = {h: {"pedidos": 0, "total": Decimal(0)} for h in range(24)}
    for p in validos:
        h = local(p.created_at).hour
        horas[h]["pedidos"] += 1
        horas[h]["total"] += Decimal(p.total)
    corte = settings.hora_corte_jornada
    por_hora = [{"hora": (corte + i) % 24, **horas[(corte + i) % 24]} for i in range(24)]

    return {
        "fecha": fecha,
        "desde": inicio,
        "hasta": fin,
        **n,
        "ticket_promedio": promedio,
        "por_modo": por_modo,
        "productos": top,
        "por_hora": por_hora,
    }


class RangoInvalido(Exception):
    """Va como 400."""


def historial(db: Session, desde: date | None, hasta: date | None) -> dict:
    hasta = hasta or hoy()
    desde = desde or hasta - timedelta(days=29)  # los últimos 30 días
    if desde > hasta:
        raise RangoInvalido("La fecha de inicio tiene que ser antes que la de fin")
    if (hasta - desde).days + 1 > MAX_DIAS_HISTORIAL:
        raise RangoInvalido(f"Como mucho {MAX_DIAS_HISTORIAL} días por consulta")

    inicio, fin = rango(desde, hasta)
    por_dia: dict[date, list[Pedido]] = defaultdict(list)
    for p in _pedidos(db, inicio, fin):
        por_dia[fecha_de_jornada(p.created_at)].append(p)

    dias = []
    d = desde
    while d <= hasta:
        n = _numeros(por_dia.get(d, []))
        n.pop("_validos")
        dias.append({"fecha": d, **n})
        d += timedelta(days=1)

    totales = {k: sum((x[k] for x in dias), Decimal(0) if isinstance(dias[0][k], Decimal) else 0) for k in dias[0] if k != "fecha"}
    return {"desde": desde, "hasta": hasta, "dias": dias, "totales": totales}
