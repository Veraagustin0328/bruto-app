import enum
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))  # "Smash Burgers", "Pizzas"...
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

    productos: Mapped[list["Producto"]] = relationship(
        back_populates="categoria", order_by="Producto.orden"
    )


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # precio base
    imagen_url: Mapped[str | None] = mapped_column(String(500))

    # Badge tipo "Recomendada", "Nuevo"... si está vacío no se muestra nada
    etiqueta: Mapped[str | None] = mapped_column(String(40))

    # visible = aparece en el menú
    # disponible = se puede pedir (la pepperoni está visible pero no disponible)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True)

    orden: Mapped[int] = mapped_column(Integer, default=0)

    categoria: Mapped[Categoria] = relationship(back_populates="productos")
    grupos: Mapped[list["GrupoOpciones"]] = relationship(
        back_populates="producto",
        order_by="GrupoOpciones.orden",
        cascade="all, delete-orphan",
    )


class TipoGrupo(str, enum.Enum):
    unica = "unica"        # elegís una sola (Simple / Doble)
    multiple = "multiple"  # elegís varias (agregados)


class GrupoOpciones(Base):
    __tablename__ = "grupos_opciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    nombre: Mapped[str] = mapped_column(String(80))  # "Tamaño", "Agregados"
    tipo: Mapped[TipoGrupo] = mapped_column(Enum(TipoGrupo, native_enum=False))
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=False)

    # Tope de opciones distintas a elegir en el grupo. None = sin tope
    max_selecciones: Mapped[int | None] = mapped_column(Integer)

    orden: Mapped[int] = mapped_column(Integer, default=0)

    producto: Mapped[Producto] = relationship(back_populates="grupos")
    opciones: Mapped[list["Opcion"]] = relationship(
        back_populates="grupo",
        order_by="Opcion.orden",
        cascade="all, delete-orphan",
    )


class Opcion(Base):
    __tablename__ = "opciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(ForeignKey("grupos_opciones.id"))
    nombre: Mapped[str] = mapped_column(String(80))  # "Doble", "Extra carne y queso"
    precio_extra: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Cuántas veces se puede pedir la misma opción.
    # 1 = normal, None = las que quieran (el extra carne y queso)
    cantidad_max: Mapped[int | None] = mapped_column(Integer, default=1)

    disponible: Mapped[bool] = mapped_column(Boolean, default=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    grupo: Mapped[GrupoOpciones] = relationship(back_populates="opciones")
