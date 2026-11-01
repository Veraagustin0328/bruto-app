from pydantic import BaseModel, ConfigDict

from app.models import TipoGrupo
from app.schemas.tipos import Precio


class OpcionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    precio_extra: Precio
    cantidad_max: int | None  # None = las que quieran
    disponible: bool


class GrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: TipoGrupo
    obligatorio: bool
    max_selecciones: int | None
    opciones: list[OpcionOut]


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: str | None
    precio: Precio
    imagen_url: str | None
    etiqueta: str | None
    disponible: bool
    grupos: list[GrupoOut]


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    productos: list[ProductoOut]
