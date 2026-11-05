"""
Dónde se guardan las fotos de los productos.

En desarrollo van a backend/uploads y las sirve FastAPI en /uploads.
Para producción (Railway borra el disco en cada deploy) hay que pasarlas a un
storage externo (Cloudinary, S3, R2...). Para eso alcanza con cambiar
guardar_archivo y borrar_archivo: el resto de la app solo usa estas dos funciones.
"""
from pathlib import Path
from uuid import uuid4

from app.config import settings

PREFIJO_URL = "/uploads"


def carpeta_uploads() -> Path:
    return Path(settings.uploads_dir)


def guardar_archivo(carpeta: str, extension: str, contenido: bytes) -> str:
    """Guarda el archivo y devuelve la URL pública."""
    if settings.storage != "local":
        raise NotImplementedError("Todavía no hay storage externo configurado")

    # Nombre random: si se cambia la foto, el celu no se queda con la vieja en caché
    nombre = f"{uuid4().hex}.{extension}"
    destino = carpeta_uploads() / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nombre).write_bytes(contenido)
    return f"{settings.backend_url}{PREFIJO_URL}/{carpeta}/{nombre}"


def borrar_archivo(url: str | None):
    """Borra un archivo que guardamos nosotros. Si no es nuestro o no está, no hace nada."""
    if not url or settings.storage != "local":
        return
    base = f"{settings.backend_url}{PREFIJO_URL}/"
    if not url.startswith(base):
        return
    raiz = carpeta_uploads().resolve()
    archivo = (raiz / url[len(base):]).resolve()
    # Que nadie me haga borrar algo fuera de uploads con un "../"
    if raiz in archivo.parents and archivo.is_file():
        archivo.unlink()
