"""Horario de la cantina, pausa y demás cosas que Renzo cambia desde el panel."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.config import Configuracion, Horario


def ahora_local() -> datetime:
    # Aparte para poder moverla en los tests
    return datetime.now(ZoneInfo(settings.zona_horaria))


def obtener_config(db: Session) -> Configuracion:
    # La fila la crea la migración. Si no está (base nueva), la armo con los valores por defecto
    config = db.get(Configuracion, 1)
    if config is None:
        config = Configuracion(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def horarios(db: Session) -> list[Horario]:
    return list(db.scalars(select(Horario).order_by(Horario.dia_semana)))


def _dentro(h: Horario, dia: int, hora: time) -> bool:
    """¿La hora cae en el turno que ARRANCÓ el día `dia`?"""
    if not h.abierto:
        return False
    if h.abre < h.cierra:  # turno normal, ej. 12:00 a 16:00
        return h.abre <= hora < h.cierra
    # Pasa la medianoche: el turno del día es desde que abre hasta las 24
    return hora >= h.abre


def esta_en_horario(db: Session, ahora: datetime | None = None) -> bool:
    lista = horarios(db)
    if not lista:
        # Sin horarios cargados no frenamos la venta (la migración los carga)
        return True

    ahora = (ahora or ahora_local()).astimezone(ZoneInfo(settings.zona_horaria))
    por_dia = {h.dia_semana: h for h in lista}
    hoy = ahora.weekday()
    hora = ahora.time().replace(tzinfo=None)

    h = por_dia.get(hoy)
    if h and _dentro(h, hoy, hora):
        return True

    # Lo que quedó del turno de ayer después de la medianoche (ej. martes 00:15
    # es parte del turno del lunes que cierra 00:30)
    ayer = (ahora - timedelta(days=1)).weekday()
    h = por_dia.get(ayer)
    return bool(h and h.abierto and h.cierra <= h.abre and hora < h.cierra)


def estado_tienda(db: Session, ahora: datetime | None = None) -> dict:
    config = obtener_config(db)
    abierto = esta_en_horario(db, ahora)
    pausado = config.pedidos_pausados

    mensaje = None
    if not abierto:
        mensaje = config.mensaje_cerrado
    elif pausado:
        mensaje = config.mensaje_pausado

    hoy = (ahora or ahora_local()).astimezone(ZoneInfo(settings.zona_horaria)).weekday()
    h = next((x for x in horarios(db) if x.dia_semana == hoy), None)

    return {
        "abierto": abierto,
        "pausado": pausado,
        "acepta_pedidos": abierto and not pausado,
        "mensaje": mensaje,
        "link_delivery": config.link_pedidosya or None,
        "horario_hoy": h if h and h.abierto else None,
    }


def motivo_para_no_aceptar(db: Session) -> str | None:
    # None = se puede pedir. Si no, el mensaje para el cliente
    estado = estado_tienda(db)
    return None if estado["acepta_pedidos"] else estado["mensaje"]
