from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pedido import PedidoOut
from app.services import pagos as mp
from app.services.pedidos import PedidoInvalido, buscar_por_codigo
from app.ws import avisar_pedido

router = APIRouter(prefix="/api/pagos", tags=["Mercado Pago"])


class LinkPago(BaseModel):
    preference_id: str
    link_pago: str


@router.post("/{codigo}/preferencia", response_model=LinkPago)
def crear_link_de_pago(codigo: str, db: Session = Depends(get_db)):
    # El celu lo llama después de crear el pedido y manda al cliente a link_pago
    try:
        return mp.crear_preferencia(db, codigo)
    except PedidoInvalido as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except mp.ErrorMercadoPago as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/{codigo}/verificar", response_model=PedidoOut)
def verificar_pago(codigo: str, avisos: BackgroundTasks, db: Session = Depends(get_db)):
    # El celu lo llama cuando el cliente vuelve de MP
    if buscar_por_codigo(db, codigo) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontramos ese pedido")
    try:
        cambiado = mp.verificar_pedido(db, codigo)
    except mp.ErrorMercadoPago as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    if cambiado is not None:
        avisos.add_task(avisar_pedido, cambiado.id, mp.evento_para_el_panel(cambiado))
    return buscar_por_codigo(db, codigo)


def procesar_pago(db: Session, pago_id: str):
    pago = mp.traer_pago(pago_id)
    return mp.aplicar_pago(db, pago) if pago else None


@router.post("/webhook", include_in_schema=False)
async def webhook(
    request: Request,
    avisos: BackgroundTasks,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    # MP manda el id del pago en la URL (?data.id=...&type=payment) y en el body
    try:
        cuerpo = await request.json()
    except Exception:
        cuerpo = {}

    tipo = request.query_params.get("type") or cuerpo.get("type")
    pago_id = request.query_params.get("data.id") or str((cuerpo.get("data") or {}).get("id") or "")

    if tipo != "payment" or not pago_id:
        return {"ok": True}  # otros avisos (merchant_order, etc.) no nos interesan

    if not mp.firma_valida(x_signature, x_request_id, pago_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma inválida")

    # Consultar a MP tarda; lo hago en otro hilo así no se frenan los WebSockets
    try:
        cambiado = await run_in_threadpool(procesar_pago, db, pago_id)
    except mp.ErrorMercadoPago:
        # 500 para que MP vuelva a intentar más tarde
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Sin token de MP")

    if cambiado is not None:
        avisos.add_task(avisar_pedido, cambiado.id, mp.evento_para_el_panel(cambiado))

    # Siempre 200 rápido: si MP no recibe 200, sigue reintentando
    return {"ok": True}
