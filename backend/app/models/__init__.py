# Importo todo acá así Alembic ve todas las tablas de una
from app.models.catalogo import Categoria, GrupoOpciones, Opcion, Producto, TipoGrupo
from app.models.pedido import (
    EstadoPago,
    EstadoPedido,
    MetodoPago,
    ModoPedido,
    Pedido,
    PedidoItem,
    PedidoItemOpcion,
)
from app.models.usuario import Rol, Usuario

__all__ = [
    "Categoria", "Producto", "GrupoOpciones", "Opcion", "TipoGrupo",
    "Pedido", "PedidoItem", "PedidoItemOpcion",
    "ModoPedido", "MetodoPago", "EstadoPago", "EstadoPedido",
    "Usuario", "Rol",
]
