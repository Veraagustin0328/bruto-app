from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Rol, Usuario
from app.security import leer_token

# tokenUrl es para que el botón "Authorize" de /docs sepa dónde loguearse
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def usuario_actual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Tu sesión venció, volvé a entrar",
        headers={"WWW-Authenticate": "Bearer"},
    )

    datos = leer_token(token)
    if datos is None:
        raise no_autorizado

    usuario = db.get(Usuario, int(datos["sub"]))
    # Si Renzo da de baja a alguien, el token que tenía deja de servir al toque
    if usuario is None or not usuario.activo:
        raise no_autorizado

    return usuario


def requiere_rol(*roles: Rol):
    # Uso: Depends(requiere_rol(Rol.admin, Rol.cantina))
    # El admin pasa siempre, no hace falta ponerlo en cada ruta
    def chequear(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol != Rol.admin and usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permiso para esto",
            )
        return usuario

    return chequear
