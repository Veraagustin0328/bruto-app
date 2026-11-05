from datetime import time

from sqlalchemy import Boolean, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

MENSAJE_CERRADO = "La cantina está cerrada. ¡Te esperamos en el próximo turno!"
MENSAJE_PAUSADO = "Estamos a full en la cocina. Pausamos los pedidos un ratito, probá en unos minutos"


class Configuracion(Base):
    # Una sola fila (id = 1) con lo que Renzo cambia desde el panel
    __tablename__ = "configuracion"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_pedidosya: Mapped[str | None] = mapped_column(String(500))

    # El botón de pánico para cuando la cocina está desbordada
    pedidos_pausados: Mapped[bool] = mapped_column(Boolean, default=False)

    mensaje_cerrado: Mapped[str] = mapped_column(String(300), default=MENSAJE_CERRADO)
    mensaje_pausado: Mapped[str] = mapped_column(String(300), default=MENSAJE_PAUSADO)


class Horario(Base):
    # Un horario por día de la semana. Si cierra antes de la hora en que abre
    # (abre 18:00, cierra 00:30) es que pasa la medianoche
    __tablename__ = "horarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia_semana: Mapped[int] = mapped_column(Integer, unique=True)  # 0 = lunes ... 6 = domingo
    abierto: Mapped[bool] = mapped_column(Boolean, default=True)  # false = ese día no abre
    abre: Mapped[time] = mapped_column(Time)
    cierra: Mapped[time] = mapped_column(Time)
