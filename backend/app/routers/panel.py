from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import requiere_rol
from app.models import EstadoPedido, Pedido, Rol, Usuario
from app.schemas.panel import CambioEstado, PedidoConAviso, PedidoPanelOut, ResumenDia
from app.services import panel as srv
from app.services.pedidos import PedidoInvalido
from app.ws import avisar_pedido

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
    # SinPermiso es un PedidoInvalido pero va como 403
    codigo = status.HTTP_403_FORBIDDEN if isinstance(e, srv.SinPermiso) else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=codigo, detail=str(e))


@router.get("/pedidos", response_model=list[PedidoPanelOut])
def listar_pedidos(
    estado: list[EstadoPedido] | None = Query(
        default=None,
        description="Filtrar por estado. Sin nada trae los activos (recibido, en preparación y listo)",
    ),
    todos: bool = Query(default=False, description="true = todos los de la jornada, incluidos entregados y cancelados"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(cantina_o_cocina),
):
    # La cocina nunca ve los de MP sin pagar. La cantina y el admin sí (con ?todos=true)
    sin_pendientes = usuario.rol == Rol.cocina
    if todos:
        return srv.pedidos_de_la_jornada(db, sin_pendientes_de_pago=sin_pendientes)
    return srv.pedidos_de_la_jornada(db, estado or srv.ACTIVOS, sin_pendientes_de_pago=sin_pendientes)


@router.get("/resumen", response_model=ResumenDia)
def resumen_del_dia(db: Session = Depends(get_db), _: Usuario = Depends(cantina)):
    return srv.resumen(db)


@router.get("/pedidos/{pedido_id}", response_model=PedidoPanelOut)
def ver_pedido(pedido: Pedido = Depends(traer_pedido), _: Usuario = Depends(cantina_o_cocina)):
    return pedido


@router.patch("/pedidos/{pedido_id}/estado", response_model=PedidoConAviso)
def cambiar_estado(
    cambio: CambioEstado,
    avisos: BackgroundTasks,
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(cantina_o_cocina),
):
    devolver_plata = cambio.estado == EstadoPedido.cancelado and srv.es_mp_pagado(pedido)
    try:
        actualizado = srv.cambiar_estado(db, pedido, cambio.estado, usuario)
    except PedidoInvalido as e:
        raise a_400(e)
    # La cocina marca "listo" y la cantina y el celu del cliente lo ven al toque
    avisos.add_task(avisar_pedido, actualizado.id, "pedido_actualizado")

    respuesta = PedidoConAviso.model_validate(actualizado)
    if devolver_plata:
        respuesta.aviso = srv.AVISO_DEVOLVER_MP
    return respuesta


@router.post("/pedidos/{pedido_id}/cobrar", response_model=PedidoPanelOut)
def cobrar(
    avisos: BackgroundTasks,
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    _: Usuario = Depends(cantina),
):
    # Marca como cobrado un pedido en efectivo
    try:
        actualizado = srv.cobrar_efectivo(db, pedido)
    except PedidoInvalido as e:
        raise a_400(e)
    avisos.add_task(avisar_pedido, actualizado.id, "pedido_actualizado")
    return actualizado


@router.post("/pedidos/{pedido_id}/cobrar-y-entregar", response_model=PedidoPanelOut)
def cobrar_y_entregar(
    avisos: BackgroundTasks,
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(cantina),
):
    # Lo que usa el chico de la cantina al dar un pedido en efectivo: cobra y entrega
    try:
        actualizado = srv.cobrar_y_entregar(db, pedido, usuario)
    except PedidoInvalido as e:
        raise a_400(e)
    avisos.add_task(avisar_pedido, actualizado.id, "pedido_actualizado")
    return actualizado


@router.post("/pedidos/{pedido_id}/reimprimir", response_model=PedidoPanelOut)
def reimprimir(
    avisos: BackgroundTasks,
    pedido: Pedido = Depends(traer_pedido),
    db: Session = Depends(get_db),
    _: Usuario = Depends(cantina),
):
    try:
        actualizado = srv.pedir_reimpresion(db, pedido)
    except PedidoInvalido as e:
        raise a_400(e)
    avisos.add_task(avisar_pedido, actualizado.id, "pedido_actualizado")
    return actualizado
