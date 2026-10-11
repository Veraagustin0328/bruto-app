import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ModoPedido(str, enum.Enum):
    comer_adentro = "comer_adentro"  # se lo llevan los chicos de BRUTO a la cancha
    take_away = "take_away"          # alguien de afuera pide y retira
    # delivery lo sumamos cuando Renzo lo pida


class MetodoPago(str, enum.Enum):
    mercadopago = "mercadopago"
    efectivo = "efectivo"


class EstadoPago(str, enum.Enum):
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"


class EstadoPedido(str, enum.Enum):
    pendiente_pago = "pendiente_pago"  # MP sin confirmar, cocina NO lo ve
    recibido = "recibido"
    en_preparacion = "en_preparacion"
    listo = "listo"
    entregado = "entregado"
    cancelado = "cancelado"


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Número corto que ve el cliente y se grita en la cantina (#042).
    # Lo asigna el service, se reinicia cada día
    numero: Mapped[int] = mapped_column(Integer, index=True)

    modo: Mapped[ModoPedido] = mapped_column(Enum(ModoPedido, native_enum=False))

    # Texto libre tipo "frente a la cancha 3". Obligatorio si es comer_adentro,
    # eso se valida en el schema
    ubicacion: Mapped[str | None] = mapped_column(String(120))

    nombre: Mapped[str] = mapped_column(String(60))
    apellido: Mapped[str] = mapped_column(String(60))
    telefono: Mapped[str] = mapped_column(String(30))
    notas: Mapped[str | None] = mapped_column(Text)

    metodo_pago: Mapped[MetodoPago] = mapped_column(Enum(MetodoPago, native_enum=False))
    estado_pago: Mapped[EstadoPago] = mapped_column(
        Enum(EstadoPago, native_enum=False), default=EstadoPago.pendiente
    )
    estado: Mapped[EstadoPedido] = mapped_column(
        Enum(EstadoPedido, native_enum=False), index=True
    )

    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    mp_preference_id: Mapped[str | None] = mapped_column(String(100))
    mp_payment_id: Mapped[str | None] = mapped_column(String(100))

    # Para el agente de impresión: cuándo salió la comanda. None = no se imprimió
    impreso_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["PedidoItem"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )


class PedidoItem(Base):
    __tablename__ = "pedido_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"))
    producto_id: Mapped[int | None] = mapped_column(
        ForeignKey("productos.id", ondelete="SET NULL")
    )

    # Copias al momento de pedir, así si cambian precios o nombres
    # los pedidos viejos quedan como estaban
    nombre_producto: Mapped[str] = mapped_column(String(120))
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # base + extras

    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    nota: Mapped[str | None] = mapped_column(String(200))  # "sin pepinillos"

    pedido: Mapped[Pedido] = relationship(back_populates="items")
    opciones: Mapped[list["PedidoItemOpcion"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class PedidoItemOpcion(Base):
    __tablename__ = "pedido_item_opciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_item_id: Mapped[int] = mapped_column(ForeignKey("pedido_items.id"))

    # Todo copiado, mismo motivo que arriba
    nombre_grupo: Mapped[str] = mapped_column(String(80))
    nombre_opcion: Mapped[str] = mapped_column(String(80))
    precio_extra: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    # Ej: 2 x "Extra carne y queso"
    cantidad: Mapped[int] = mapped_column(Integer, default=1)

    item: Mapped[PedidoItem] = relationship(back_populates="opciones")
