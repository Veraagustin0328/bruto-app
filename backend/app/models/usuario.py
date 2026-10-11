import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Rol(str, enum.Enum):
    admin = "admin"      # Renzo: todo, incluido carta y precios
    cantina = "cantina"  # los chicos de BRUTO: pedidos y cobros
    cocina = "cocina"    # solo la pantalla de comandas


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[Rol] = mapped_column(Enum(Rol, native_enum=False))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
