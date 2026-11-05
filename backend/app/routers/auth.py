from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import limites
from app.database import get_db
from app.deps import requiere_rol, usuario_actual
from app.models import Rol, Usuario
from app.schemas.usuario import LoginOut, UsuarioCambios, UsuarioNuevo, UsuarioOut
from app.security import crear_token, hashear_password, verificar_password

router = APIRouter(prefix="/api/auth", tags=["Login y usuarios"])


@router.post("/login", response_model=LoginOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Va como formulario (username + password) porque es el estándar de OAuth2
    # y así funciona el botón "Authorize" de /docs. En username va el email
    email = form.username.strip().lower()

    # Muchas claves mal seguidas: ese email queda bloqueado un rato, aunque ahora la ponga bien
    falta = limites.segundos_de_bloqueo(email)
    if falta:
        minutos = max(1, round(falta / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muchos intentos fallidos. Probá de nuevo en {minutos} minutos",
        )

    usuario = db.scalar(select(Usuario).where(Usuario.email == email))

    # Mismo mensaje si no existe o si la clave está mal, así no se puede
    # averiguar qué emails están registrados
    if usuario is None or not verificar_password(form.password, usuario.password_hash):
        limites.anotar_login_fallido(email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    limites.anotar_login_ok(email)
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu usuario está dado de baja, hablá con Renzo",
        )

    return LoginOut(access_token=crear_token(usuario.id, usuario.rol.value), usuario=usuario)


@router.get("/yo", response_model=UsuarioOut)
def quien_soy(usuario: Usuario = Depends(usuario_actual)):
    # El front lo usa al abrir el panel para saber si sigue logueado y qué rol tiene
    return usuario


# ---------- usuarios: solo el admin ----------


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(Rol.admin))
):
    return db.scalars(select(Usuario).order_by(Usuario.nombre)).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioNuevo,
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_rol(Rol.admin)),
):
    if db.scalar(select(Usuario).where(Usuario.email == datos.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya hay un usuario con ese email")

    usuario = Usuario(
        nombre=datos.nombre.strip(),
        email=datos.email,
        password_hash=hashear_password(datos.password),
        rol=datos.rol,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
def editar_usuario(
    usuario_id: int,
    cambios: UsuarioCambios,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requiere_rol(Rol.admin)),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe ese usuario")

    # Que el admin no se deje afuera solo por error
    if usuario.id == admin.id and (cambios.activo is False or (cambios.rol and cambios.rol != Rol.admin)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No te podés dar de baja ni sacarte el admin a vos mismo",
        )

    if cambios.nombre is not None:
        usuario.nombre = cambios.nombre.strip()
    if cambios.password is not None:
        usuario.password_hash = hashear_password(cambios.password)
    if cambios.rol is not None:
        usuario.rol = cambios.rol
    if cambios.activo is not None:
        usuario.activo = cambios.activo

    db.commit()
    db.refresh(usuario)
    return usuario
