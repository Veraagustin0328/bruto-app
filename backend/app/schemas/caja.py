from datetime import date, datetime

from pydantic import BaseModel

from app.models import ModoPedido
from app.schemas.tipos import Precio


class NumerosCaja(BaseModel):
    pedidos: int  # los que llegaron a la cocina (sin cancelados ni MP sin pagar)
    vendido: Precio  # lo cobrado: MP + efectivo
    mercadopago: Precio
    efectivo_cobrado: Precio
    efectivo_a_cobrar: Precio
    cancelados: int  # cancelados que habían entrado a la cocina
    mp_sin_pagar: int  # pedidos de MP que nadie pagó y se cancelaron solos


class PorModo(BaseModel):
    modo: ModoPedido
    pedidos: int
    total: Precio


class ProductoVendido(BaseModel):
    nombre: str
    cantidad: int
    total: Precio


class VentaPorHora(BaseModel):
    hora: int  # 0 a 23, hora de Mendoza
    pedidos: int
    total: Precio


class CajaDia(NumerosCaja):
    fecha: date  # el día en que arrancó la jornada
    desde: datetime  # 6 AM de ese día
    hasta: datetime  # 6 AM del día siguiente
    ticket_promedio: Precio
    por_modo: list[PorModo]
    productos: list[ProductoVendido]  # los 10 más vendidos
    por_hora: list[VentaPorHora]  # las 24 horas, en el orden de la jornada (6, 7... 5)


class DiaHistorial(NumerosCaja):
    fecha: date


class CajaHistorial(BaseModel):
    desde: date
    hasta: date
    dias: list[DiaHistorial]
    totales: NumerosCaja
