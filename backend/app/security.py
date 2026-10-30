import bcrypt


def hashear_password(password: str) -> str:
    # bcrypt solo mira los primeros 72 bytes, más que eso no tiene sentido
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
