from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import EstadoPago, EstadoPedido, MetodoPago, ModoPedido
from app.schemas.pedido import ItemOut
from app.schemas.tipos import Precio


class PedidoPanelOut(BaseModel):
    # Lo mismo que ve el cliente, más lo que necesita la cantina:
    # id, teléfono y si ya salió la comanda
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: int
    modo: ModoPedido
    ubicacion: str | None
    nombre: str
    apellido: str
    telefono: str
    metodo_pago: MetodoPago
    estado_pago: EstadoPago
    estado: EstadoPedido
    total: Precio
    notas: str | None
    items: list[ItemOut]
    impreso_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PedidoConAviso(PedidoPanelOut):
    # Para avisarle algo a quien hizo el cambio, ej: que devuelva la plata de MP
    aviso: str | None = None


class CambioEstado(BaseModel):
    estado: EstadoPedido


class ResumenDia(BaseModel):
    # Los cuadritos de arriba del panel
    pedidos: int
    vendido: Precio
    efectivo_a_cobrar: Precio
    esperando_pago_mp: int
