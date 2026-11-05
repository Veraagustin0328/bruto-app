"""Schemas del ABM de la carta (solo Renzo, salvo prender/apagar)."""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import TipoGrupo
from app.schemas.tipos import Precio

PrecioIn = Field(ge=0, le=10_000_000, max_digits=12, decimal_places=2)


# ---------- lo que ve el admin: todo, incluido lo apagado ----------


class OpcionAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grupo_id: int
    nombre: str
    precio_extra: Precio
    cantidad_max: int | None
    disponible: bool
    orden: int


class GrupoAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    producto_id: int
    nombre: str
    tipo: TipoGrupo
    obligatorio: bool
    max_selecciones: int | None
    orden: int
    opciones: list[OpcionAdmin]


class ProductoAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    categoria_id: int
    nombre: str
    descripcion: str | None
    precio: Precio
    imagen_url: str | None
    etiqueta: str | None
    visible: bool
    disponible: bool
    orden: int
    grupos: list[GrupoAdmin]


class CategoriaAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    orden: int
    activa: bool
    productos: list[ProductoAdmin]


# ---------- altas y cambios ----------
# En los "Cambios" todo es opcional: se cambia solo lo que venga.
# Ojo con cantidad_max y max_selecciones: null quiere decir "sin tope",
# así que se mira si vino el campo (model_fields_set), no si es None


class CategoriaNueva(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    activa: bool = True


class CategoriaCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    activa: bool | None = None


class ProductoNuevo(BaseModel):
    categoria_id: int
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    precio: Decimal = PrecioIn
    etiqueta: str | None = Field(default=None, max_length=40)
    visible: bool = True
    disponible: bool = True


class ProductoCambios(BaseModel):
    categoria_id: int | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    precio: Decimal | None = Field(default=None, ge=0, le=10_000_000, max_digits=12, decimal_places=2)
    etiqueta: str | None = Field(default=None, max_length=40)
    visible: bool | None = None
    disponible: bool | None = None


class GrupoNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    tipo: TipoGrupo
    obligatorio: bool = False
    max_selecciones: int | None = Field(default=None, ge=1)


class GrupoCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    tipo: TipoGrupo | None = None
    obligatorio: bool | None = None
    max_selecciones: int | None = Field(default=None, ge=1)


class OpcionNueva(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    precio_extra: Decimal = PrecioIn
    cantidad_max: int | None = Field(default=1, ge=1)  # null = las que quieran
    disponible: bool = True


class OpcionCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    precio_extra: Decimal | None = Field(default=None, ge=0, le=10_000_000, max_digits=12, decimal_places=2)
    cantidad_max: int | None = Field(default=None, ge=1)
    disponible: bool | None = None


class NuevoOrden(BaseModel):
    # Todos los ids, en el orden nuevo
    ids: list[int] = Field(min_length=1)


class Disponibilidad(BaseModel):
    disponible: bool


# ---------- aumento masivo de precios ----------


class AumentoPrecios(BaseModel):
    aplica_a: Literal["todo", "categoria", "productos"]
    categoria_id: int | None = None
    producto_ids: list[int] | None = None
    porcentaje: Decimal = Field(gt=-50, le=200, description="10 = sube 10 %. Negativo baja")
    redondeo: Literal[100, 500, 1000] = 100

    @model_validator(mode="after")
    def validar_alcance(self):
        if self.aplica_a == "categoria" and self.categoria_id is None:
            raise ValueError("Falta categoria_id")
        if self.aplica_a == "productos" and not self.producto_ids:
            raise ValueError("Falta la lista de producto_ids")
        return self


class OpcionPrecioNuevo(BaseModel):
    opcion_id: int
    grupo: str
    nombre: str
    # El extra es lo que se guarda; el final (simple + extra) es lo que ve el cliente
    extra_viejo: Precio
    extra_nuevo: Precio
    final_viejo: Precio
    final_nuevo: Precio


class ProductoPrecioNuevo(BaseModel):
    producto_id: int
    nombre: str
    categoria: str
    precio_viejo: Precio
    precio_nuevo: Precio
    opciones: list[OpcionPrecioNuevo]


class VistaPreviaAumento(BaseModel):
    productos: list[ProductoPrecioNuevo]
    cantidad_precios: int  # para el botón "Aplicar a 10 precios"
