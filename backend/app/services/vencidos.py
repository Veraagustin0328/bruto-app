"""
Pedidos de Mercado Pago que nadie pagó.

Si alguien elige MP y no paga, el pedido queda en pendiente_pago para siempre.
Una tarea de fondo (ver app/main.py) corre esto cada minuto: los que pasaron
el tiempo para pagar se cancelan, salvo que MP diga que sí se pagaron.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import EstadoPedido, Pedido
from app.services import pagos

log = logging.getLogger("bruto.vencidos")


def pedidos_vencidos(db: Session, ahora: datetime | None = None) -> list[Pedido]:
    ahora = ahora or datetime.now(timezone.utc)
    limite = (ahora - timedelta(minutes=settings.minutos_para_pagar)).astimezone(timezone.utc)
    return list(
        db.scalars(
            select(Pedido)
            .where(Pedido.estado == EstadoPedido.pendiente_pago, Pedido.created_at < limite)
            .order_by(Pedido.id)
        )
    )


def revisar_vencidos(db: Session, ahora: datetime | None = None) -> list[tuple[int, str]]:
    """Cancela los vencidos. Devuelve (id, evento) de cada pedido que cambió,
    para avisar por WebSocket."""
    # Sin token de MP no hay pagos que esperar ni a quién preguntar
    if not settings.mp_access_token:
        return []

    cambios = []
    for pedido in pedidos_vencidos(db, ahora):
        # Antes de cancelar le pregunto a MP, por si pagó y el aviso no llegó
        try:
            pagos.verificar_pedido(db, pedido.codigo)
        except Exception as e:
            # MP caído o sin internet: no cancelo a ciegas, pruebo en la próxima vuelta
            log.warning("No pude consultar a MP por el pedido #%s: %s", pedido.numero, e)
            db.rollback()
            continue

        db.refresh(pedido)
        if pedido.estado == EstadoPedido.recibido:
            log.info("Pedido #%s estaba pagado y no nos había llegado el aviso", pedido.numero)
            cambios.append((pedido.id, "pedido_nuevo"))
        elif pedido.estado == EstadoPedido.pendiente_pago:
            pedido.estado = EstadoPedido.cancelado
            db.commit()
            log.info("Pedido #%s cancelado: no se pagó a tiempo", pedido.numero)
            cambios.append((pedido.id, "pedido_actualizado"))
    return cambios


def _revisar_con_sesion() -> list[tuple[int, str]]:
    with SessionLocal() as db:
        return revisar_vencidos(db)


async def una_vuelta():
    # La consulta a MP es bloqueante, va en otro hilo así no frena los WebSockets
    from app.ws import avisar_pedido

    cambios = await asyncio.to_thread(_revisar_con_sesion)
    for pedido_id, evento in cambios:
        await avisar_pedido(pedido_id, evento)


async def revisar_cada_tanto():
    # Corre mientras viva la app. Si una vuelta falla, sigue con la próxima
    while True:
        await asyncio.sleep(settings.segundos_entre_revisiones)
        try:
            await una_vuelta()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Falló la revisión de pedidos sin pagar")
