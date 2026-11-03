from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

ALGORITMO = "HS256"


def hashear_password(password: str) -> str:
    # bcrypt solo mira los primeros 72 bytes, más que eso no tiene sentido
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def crear_token(usuario_id: int, rol: str) -> str:
    ahora = datetime.now(timezone.utc)
    datos = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.jwt_expira_minutos),
    }
    return jwt.encode(datos, settings.jwt_secret, algorithm=ALGORITMO)


def leer_token(token: str) -> dict | None:
    # Devuelve None si el token es trucho o ya venció
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        return None
