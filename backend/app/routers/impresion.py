"""
Lo que usa el agente de impresión (print-agent) que corre en la PC de la cantina.

Entra con un usuario de rol "impresora": solo puede leer las comandas
pendientes y marcarlas impresas. El admin también pasa, para probar.
Además puede escuchar /ws/impresion para enterarse al toque (pedido nuevo o reimprimir).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import requiere_rol
from app.models import Pedido, Rol, Usuario
from app.schemas.panel import PedidoPanelOut
from app.services import panel as srv
from app.ws import avisar_pedido

router = APIRouter(prefix="/api/impresion", tags=["Ticketera"])

impresora = requiere_rol(Rol.impresora)


@router.get("/pendientes", response_model=list[PedidoPanelOut])
def pendientes(db: Session = Depends(get_db), _: Usuario = Depends(impresora)):
    # Recibidos o en preparación de la jornada que todavía no salieron por la ticketera
    return srv.pendientes_de_imprimir(db)


@router.post("/pedidos/{pedido_id}/impreso", response_model=PedidoPanelOut)
def marcar_impreso(
    pedido_id: int, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(impresora),
):
    pedido: Pedido | None = srv.buscar(db, pedido_id)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe ese pedido")
    actualizado = srv.marcar_impreso(db, pedido)
    # Así en el panel se ve que la comanda ya salió
    avisos.add_task(avisar_pedido, actualizado.id, "pedido_actualizado")
    return actualizado
