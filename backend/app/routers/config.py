"""Configuración de la cantina: horario, pausa, mensajes y link de delivery. Solo admin."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import requiere_rol
from app.models import Horario, Rol, Usuario
from app.schemas.config import ConfigCambios, ConfigOut, HorariosIn
from app.services import config as srv

router = APIRouter(prefix="/api/config", tags=["Configuración"])

solo_admin = requiere_rol(Rol.admin)


def armar(db: Session) -> ConfigOut:
    config = srv.obtener_config(db)
    salida = ConfigOut.model_validate(config)
    salida.horarios = srv.horarios(db)
    return salida


@router.get("", response_model=ConfigOut)
def ver_config(db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    return armar(db)


@router.patch("", response_model=ConfigOut)
def editar_config(cambios: ConfigCambios, db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    config = srv.obtener_config(db)
    for campo in cambios.model_fields_set:
        valor = getattr(cambios, campo)
        # El link se puede borrar mandando null; lo demás, null = no tocar
        if valor is None and campo != "link_pedidosya":
            continue
        setattr(config, campo, valor.strip() if isinstance(valor, str) else valor)
    db.commit()
    return armar(db)


@router.put("/horarios", response_model=ConfigOut)
def cambiar_horarios(datos: HorariosIn, db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
    # Reemplaza los 7 días de una
    actuales = {h.dia_semana: h for h in srv.horarios(db)}
    for dia in datos.dias:
        h = actuales.get(dia.dia_semana) or Horario(dia_semana=dia.dia_semana)
        h.abierto, h.abre, h.cierra = dia.abierto, dia.abre, dia.cierra
        db.add(h)
    db.commit()
    return armar(db)
