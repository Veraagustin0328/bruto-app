from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import requiere_rol
from app.models import EstadoPedido, Pedido, Rol, Usuario
from app.schemas.panel import CambioEstado, PedidoPanelOut, ResumenDia
from app.services import panel as srv
from app.services.pedidos import PedidoInvalido

router = APIRouter(prefix="/api/panel", tags=["Panel de la cantina"])

# Quién entra a qué. El admin pasa siempre (lo resuelve requiere_rol)
cantina = requiere_rol(Rol.cantina)
cantina_o_cocina = requiere_rol(Rol.cantina, Rol.cocina)


def traer_pedido(pedido_id: int, db: Session = Depends(get_db)) -> Pedido:
    pedido = srv.buscar(db, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe ese pedido")
    return pedido


def a_400(e: PedidoInvalido):
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/pedidos", response_model=list[PedidoPanelOut])
def listar_pedidos(
    estado: list[EstadoPedido] | None = Query(
        default=None,
        description="Filtrar por estado. Sin nada trae los activos (recibido, en preparación y listo)",
    ),
    todos: bool = Query(default=False, description="true = todos los de la jornada, incluidos entregados y cancelados"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(cantina_o_cocina),
):
    if todos:
        return srv.pedidos_de_la_jornada(db)
    return srv.pedidos_de_la_jornada(db, estado or srv.ACTIVOS)


@router.get("/resumen", response_model=ResumenDia)
def resumen_del_dia(db: Session = Depends(get_db), _: Usuario = Depends(cantina)):
    return srv.resumen(db)


@router.get("/pedidos/{pedido_id}", response_model=PedidoPanelOut)
def ver_pedido(pedido: Pedido = Depends(traer_pedido), _: Usuario = Depends(cantina_o_cocina)):
    return pedido


@router.patch("/pedidos/{pedido_id}/estado", response_model=PedidoPanelOut)
def cambiar_estado(
    cambio: CambioEstado,
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(cantina_o_cocina),
):
    try:
        return srv.cambiar_estado(db, pedido, cambio.estado, usuario)
    except PedidoInvalido as e:
        raise a_400(e)


@router.post("/pedidos/{pedido_id}/cobrar", response_model=PedidoPanelOut)
def cobrar(
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    _: Usuario = Depends(cantina),
):
    # Marca como cobrado un pedido en efectivo
    try:
        return srv.cobrar_efectivo(db, pedido)
    except PedidoInvalido as e:
        raise a_400(e)


@router.post("/pedidos/{pedido_id}/reimprimir", response_model=PedidoPanelOut)
def reimprimir(
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    _: Usuario = Depends(cantina),
):
    try:
        return srv.pedir_reimpresion(db, pedido)
    except PedidoInvalido as e:
        raise a_400(e)
