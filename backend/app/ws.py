"""
Tiempo real con WebSockets.

Hay tres tipos de "salas":
- "panel": la cantina, la cocina y el admin. Reciben todos los pedidos.
- "impresion": el agente de la ticketera. Recibe lo que hay que imprimir.
- "pedido:<codigo>": el celu del cliente. Recibe solo su pedido.

Ojo: las conexiones viven en la memoria de este proceso. Con un solo
proceso de uvicorn (que es lo que necesita una cantina) anda perfecto.
Si algún día se corre con varios workers, hay que pasar esto a Redis.
"""
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import EstadoPedido, Pedido, PedidoItem, Rol, Usuario
from app.schemas.panel import PedidoPanelOut
from app.schemas.pedido import PedidoOut
from app.security import leer_token

router = APIRouter()


class Salas:
    def __init__(self):
        self.conexiones: dict[str, set[WebSocket]] = defaultdict(set)

    async def entrar(self, sala: str, ws: WebSocket):
        await ws.accept()
        self.conexiones[sala].add(ws)

    def salir(self, sala: str, ws: WebSocket):
        self.conexiones[sala].discard(ws)
        if not self.conexiones[sala]:
            del self.conexiones[sala]

    async def mandar(self, sala: str, mensaje: dict):
        # Copio el set porque si alguien se desconecta mientras mando, se modifica
        for ws in list(self.conexiones.get(sala, ())):
            try:
                await ws.send_json(mensaje)
            except Exception:
                # Se le cortó la conexión (celu sin señal, pestaña cerrada). Lo saco
                self.salir(sala, ws)


salas = Salas()


async def escuchar_hasta_que_corte(ws: WebSocket):
    # Mantiene viva la conexión. El front manda "ping" cada tanto y le
    # contestamos "pong"; así se nota si se cayó el wifi de la cantina
    while True:
        texto = await ws.receive_text()
        if texto == "ping":
            await ws.send_text("pong")


@router.websocket("/ws/panel")
async def ws_panel(ws: WebSocket, token: str = ""):
    # El navegador no deja mandar headers en un WebSocket,
    # por eso el token viene en la URL: /ws/panel?token=...
    datos = leer_token(token)
    usuario = None
    if datos:
        with SessionLocal() as db:
            usuario = db.get(Usuario, int(datos["sub"]))

    if usuario is None or not usuario.activo or usuario.rol not in (Rol.admin, Rol.cantina, Rol.cocina):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await salas.entrar("panel", ws)
    try:
        await escuchar_hasta_que_corte(ws)
    except WebSocketDisconnect:
        pass
    finally:
        salas.salir("panel", ws)


@router.websocket("/ws/impresion")
async def ws_impresion(ws: WebSocket, token: str = ""):
    # El agente de la ticketera (rol impresora). El admin también, para probar
    datos = leer_token(token)
    usuario = None
    if datos:
        with SessionLocal() as db:
            usuario = db.get(Usuario, int(datos["sub"]))

    if usuario is None or not usuario.activo or usuario.rol not in (Rol.admin, Rol.impresora):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await salas.entrar("impresion", ws)
    try:
        await escuchar_hasta_que_corte(ws)
    except WebSocketDisconnect:
        pass
    finally:
        salas.salir("impresion", ws)


@router.websocket("/ws/pedido/{codigo}")
async def ws_pedido(ws: WebSocket, codigo: str):
    # El celu del cliente. No pide login: el código largo y random ya hace de llave
    with SessionLocal() as db:
        existe = db.scalar(select(Pedido.id).where(Pedido.codigo == codigo))
    if existe is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    sala = f"pedido:{codigo}"
    await salas.entrar(sala, ws)
    try:
        await escuchar_hasta_que_corte(ws)
    except WebSocketDisconnect:
        pass
    finally:
        salas.salir(sala, ws)


async def avisar_pedido(pedido_id: int, evento: str):
    """Manda el pedido actualizado a la cantina y al celu del cliente.

    Se llama como background task desde las rutas: primero se responde
    al que hizo el cambio y después se avisa a todos los demás.
    evento: "pedido_nuevo" o "pedido_actualizado". Cuando MP aprueba un pago
    (pendiente_pago -> recibido) hay que mandar "pedido_nuevo", así suena en la cantina
    """
    with SessionLocal() as db:
        pedido = db.scalar(
            select(Pedido)
            .where(Pedido.id == pedido_id)
            .options(selectinload(Pedido.items).selectinload(PedidoItem.opciones))
        )
        if pedido is None:
            return
        para_panel = PedidoPanelOut.model_validate(pedido).model_dump(mode="json")
        para_cliente = PedidoOut.model_validate(pedido).model_dump(mode="json")
        codigo = pedido.codigo
        sin_pagar = pedido.estado == EstadoPedido.pendiente_pago

    # Un pedido de MP sin pagar todavía no existe para la cantina ni la cocina
    if not sin_pagar:
        await salas.mandar("panel", {"evento": evento, "pedido": para_panel})
        # Pedido que recién entra a la cocina: que salga la comanda
        if evento == "pedido_nuevo":
            await salas.mandar("impresion", {"evento": "imprimir", "pedido": para_panel})
    await salas.mandar(f"pedido:{codigo}", {"evento": "pedido_actualizado", "pedido": para_cliente})


async def avisar_impresora(pedido_id: int):
    # Para "reimprimir": le manda el pedido al agente de la ticketera
    with SessionLocal() as db:
        pedido = db.scalar(
            select(Pedido)
            .where(Pedido.id == pedido_id)
            .options(selectinload(Pedido.items).selectinload(PedidoItem.opciones))
        )
        if pedido is None:
            return
        datos = PedidoPanelOut.model_validate(pedido).model_dump(mode="json")
    await salas.mandar("impresion", {"evento": "imprimir", "pedido": datos})


async def avisar_carta():
    # Cambió algo de la carta (precio, stock, producto nuevo): la cantina la recarga
    await salas.mandar("panel", {"evento": "carta_actualizada"})


async def avisar_config():
    # Pausaron los pedidos, cambió el horario o el link: los paneles abiertos se actualizan
    await salas.mandar("panel", {"evento": "config_actualizada"})
