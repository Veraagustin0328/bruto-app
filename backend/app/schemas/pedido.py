import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import EstadoPago, EstadoPedido, MetodoPago, ModoPedido
from app.schemas.tipos import Precio

# ---------- lo que manda el celu ----------


class OpcionElegida(BaseModel):
    opcion_id: int
    cantidad: int = Field(default=1, ge=1, le=10)


class ItemNuevo(BaseModel):
    producto_id: int
    cantidad: int = Field(default=1, ge=1, le=20)
    opciones: list[OpcionElegida] = Field(default_factory=list, max_length=20)
    nota: str | None = Field(default=None, max_length=200)

    @field_validator("nota")
    @classmethod
    def limpiar_nota(cls, v):
        v = (v or "").strip()
        return v or None


class PedidoNuevo(BaseModel):
    modo: ModoPedido
    ubicacion: str | None = Field(default=None, max_length=120)

    nombre: str = Field(min_length=2, max_length=60)
    apellido: str = Field(min_length=2, max_length=60)
    telefono: str

    metodo_pago: MetodoPago
    notas: str | None = Field(default=None, max_length=300)

    items: list[ItemNuevo] = Field(min_length=1, max_length=30)

    @field_validator("nombre", "apellido")
    @classmethod
    def limpiar_texto(cls, v: str):
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("tiene que tener al menos 2 letras")
        return v

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: str):
        # Aceptamos "261 555-0142", "+54 9 261 5550142", etc. Guardamos solo números
        solo_numeros = re.sub(r"\D", "", v)
        if not 8 <= len(solo_numeros) <= 15:
            raise ValueError("el teléfono no parece válido")
        return solo_numeros

    @model_validator(mode="after")
    def validar_ubicacion(self):
        ubicacion = " ".join((self.ubicacion or "").split())

        if self.modo == ModoPedido.comer_adentro:
            if len(ubicacion) < 3:
                raise ValueError("Para comer adentro hace falta decir dónde estás")
            self.ubicacion = ubicacion
        else:
            # En take away no tiene sentido guardar una ubicación
            self.ubicacion = None

        return self


# ---------- lo que devolvemos ----------


class ItemOpcionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre_grupo: str
    nombre_opcion: str
    precio_extra: Precio
    cantidad: int


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre_producto: str
    precio_unitario: Precio
    cantidad: int
    nota: str | None
    opciones: list[ItemOpcionOut]


class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    numero: int
    modo: ModoPedido
    ubicacion: str | None
    nombre: str
    apellido: str
    metodo_pago: MetodoPago
    estado_pago: EstadoPago
    estado: EstadoPedido
    total: Precio
    notas: str | None
    items: list[ItemOut]
    created_at: datetime
