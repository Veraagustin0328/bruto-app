"""Configuración de la cantina: horario, pausa, mensajes y link de delivery.

Todo solo admin, salvo pausar y despausar los pedidos, que también lo hace la
cantina (si a la noche Renzo no está y la cocina explota, lo tienen que poder frenar).
Cada cambio le avisa "config_actualizada" a los paneles abiertos.
"""
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import requiere_rol
from app.models import Horario, Rol, Usuario
from app.schemas.config import ConfigCambios, ConfigOut, HorariosIn, PausaIn, PausaOut
from app.services import config as srv
from app.ws import avisar_config

router = APIRouter(prefix="/api/config", tags=["Configuración"])

solo_admin = requiere_rol(Rol.admin)
admin_o_cantina = requiere_rol(Rol.cantina)


def armar(db: Session) -> ConfigOut:
    config = srv.obtener_config(db)
    salida = ConfigOut.model_validate(config)
    salida.horarios = srv.horarios(db)
    return salida


@router.get("", response_model=ConfigOut)
def ver_config(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    return armar(db)


@router.patch("", response_model=ConfigOut)
def editar_config(
    cambios: ConfigCambios, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    config = srv.obtener_config(db)
    for campo in cambios.model_fields_set:
        valor = getattr(cambios, campo)
        # El link se puede borrar mandando null; lo demás, null = no tocar
        if valor is None and campo != "link_pedidosya":
            continue
        setattr(config, campo, valor.strip() if isinstance(valor, str) else valor)
    db.commit()
    avisos.add_task(avisar_config)
    return armar(db)


@router.put("/horarios", response_model=ConfigOut)
def cambiar_horarios(
    datos: HorariosIn, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    # Reemplaza los 7 días de una
    actuales = {h.dia_semana: h for h in srv.horarios(db)}
    for dia in datos.dias:
        h = actuales.get(dia.dia_semana) or Horario(dia_semana=dia.dia_semana)
        h.abierto, h.abre, h.cierra = dia.abierto, dia.abre, dia.cierra
        db.add(h)
    db.commit()
    avisos.add_task(avisar_config)
    return armar(db)


# ---------- pausa: admin y cantina ----------


@router.get("/pausa", response_model=PausaOut)
def ver_pausa(db: Session = Depends(get_db), _: Usuario = Depends(admin_o_cantina)):
    return srv.obtener_config(db)


@router.put("/pausa", response_model=PausaOut)
def pausar(
    datos: PausaIn, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(admin_o_cantina),
):
    # Se manda el valor (no un "toggle"): si dos celus tocan a la vez no queda al revés
    config = srv.obtener_config(db)
    config.pedidos_pausados = datos.pausado
    db.commit()
    avisos.add_task(avisar_config)
    return config
