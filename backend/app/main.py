import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import ws
from app.config import settings
from app.routers import auth, carta, pagos, panel, tienda
from app.services.vencidos import revisar_cada_tanto


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar: la tarea que cancela los pedidos de MP que nadie pagó
    tarea = asyncio.create_task(revisar_cada_tanto())
    app.state.tarea_vencidos = tarea
    yield
    # Al apagar: la corto prolijo
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass


app = FastAPI(title="BRUTO API", version="0.1.0", lifespan=lifespan)

# El front (React) corre en otro puerto/dominio, sin esto el navegador
# le bloquea las llamadas a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tienda.router)
app.include_router(auth.router)
app.include_router(panel.router)
app.include_router(pagos.router)
app.include_router(carta.router)
app.include_router(ws.router)


@app.get("/api/salud", tags=["Sistema"])
def salud():
    # Para chequear rápido que el backend está vivo (y después para Railway)
    return {"ok": True}
