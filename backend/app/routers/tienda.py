import re

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import limites
from app.config import settings
from app.database import get_db
from app.models import Categoria, GrupoOpciones, Producto
from app.schemas.catalogo import CategoriaOut
from app.schemas.config import EstadoTienda
from app.schemas.pedido import PedidoNuevo, PedidoOut
from app.services.config import estado_tienda, motivo_para_no_aceptar
from app.services.pedidos import (
    PedidoInvalido,
    activos_del_telefono,
    buscar_por_clave,
    buscar_por_codigo,
    crear_o_repetir,
)
from app.ws import avisar_pedido

# Todo lo de acá es público: lo usa el cliente desde el celu, sin login
router = APIRouter(prefix="/api/tienda", tags=["Tienda"])


@router.get("/menu", response_model=list[CategoriaOut])
def ver_menu(db: Session = Depends(get_db)):
    # Traigo todo en pocas consultas (selectinload) en vez de una por producto
    categorias = db.scalars(
        select(Categoria)
        .where(Categoria.activa.is_(True))
        .order_by(Categoria.orden)
        .options(
            selectinload(Categoria.productos)
            .selectinload(Producto.grupos)
            .selectinload(GrupoOpciones.opciones)
        )
    ).all()

    menu = []
    for cat in categorias:
        # Los no visibles no se muestran. Los no disponibles sí (la pepperoni
        # "próximamente" o la bondiola sin stock), el front los muestra apagados
        productos = [p for p in cat.productos if p.visible]
        if not productos:
            continue
        menu.append(CategoriaOut(id=cat.id, nombre=cat.nombre, productos=productos))

    return menu


@router.get("/estado", response_model=EstadoTienda)
def ver_estado(db: Session = Depends(get_db)):
    # Para el cartel de "Cantina abierta" / "Cerrado" y el botón de delivery
    return estado_tienda(db)


def leer_clave(clave: str | None) -> str | None:
    # El celu manda un crypto.randomUUID() por intento. Acepto algo parecido y nada raro
    if clave is None:
        return None
    clave = clave.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", clave):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El Idempotency-Key tiene que tener entre 8 y 64 letras, números o guiones",
        )
    return clave


@router.post(
    "/pedidos",
    response_model=PedidoOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Ese Idempotency-Key ya se usó: devuelve el pedido que ya existía"}},
)
def hacer_pedido(
    datos: PedidoNuevo,
    request: Request,
    response: Response,
    avisos: BackgroundTasks,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Un código random por intento de checkout. Si se repite, no se crea otro pedido",
    ),
):
    clave = leer_clave(idempotency_key)

    # Reintento con mala señal: el pedido ya entró la primera vez. Lo devuelvo
    # antes de mirar horario y límites (no cuenta como pedido nuevo)
    if clave:
        existente = buscar_por_clave(db, clave)
        if existente is not None:
            response.status_code = status.HTTP_200_OK
            return existente

    # Cerrado o pausado (cocina desbordada): no entra nada
    motivo = motivo_para_no_aceptar(db)
    if motivo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=motivo)

    # La tienda es pública: freno a los que mandan pedidos en ráfaga
    ip = limites.ip_del_cliente(request)
    if not limites.puede_pedir(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Hiciste muchos pedidos seguidos, esperá unos minutos",
        )
    if activos_del_telefono(db, datos.telefono) >= settings.limite_activos_por_telefono:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Ya tenés varios pedidos en curso con este teléfono. Esperá a que salgan y pedí de nuevo",
        )

    try:
        pedido, es_nuevo = crear_o_repetir(db, datos, clave)
    except PedidoInvalido as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not es_nuevo:
        # Dos reintentos casi juntos: el otro ya lo creó y avisó
        response.status_code = status.HTTP_200_OK
        return buscar_por_codigo(db, pedido.codigo)

    # Solo cuento los que entraron: un error del cliente no le gasta el cupo
    limites.anotar_pedido(ip)

    # Le cae al panel de la cantina al toque, sin que nadie recargue
    avisos.add_task(avisar_pedido, pedido.id, "pedido_nuevo")

    # Recargo con items y opciones para devolverlo completo
    return buscar_por_codigo(db, pedido.codigo)


@router.get("/pedidos/{codigo}", response_model=PedidoOut)
def ver_pedido(codigo: str, db: Session = Depends(get_db)):
    # Lo usa la pantalla de seguimiento del celu
    pedido = buscar_por_codigo(db, codigo)
    if pedido is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontramos ese pedido")
    return pedido
