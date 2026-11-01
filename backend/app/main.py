from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import tienda

app = FastAPI(title="BRUTO API", version="0.1.0")

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


@app.get("/api/salud", tags=["Sistema"])
def salud():
    # Para chequear rápido que el backend está vivo (y después para Railway)
    return {"ok": True}
