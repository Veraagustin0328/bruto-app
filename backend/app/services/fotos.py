"""Fotos de los productos: valida, achica a 800 px y convierte a webp."""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app import storage

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LADO_MAX = 800
FORMATOS = {"JPEG", "PNG", "WEBP"}

# Una foto de 20.000 x 20.000 px pesa poco comprimida pero revienta la memoria
# al abrirla. Más de esto no tiene sentido para una foto de producto
Image.MAX_IMAGE_PIXELS = 40_000_000


class FotoInvalida(Exception):
    """El mensaje es para mostrárselo a Renzo tal cual."""


def procesar(contenido: bytes) -> bytes:
    if len(contenido) > MAX_BYTES:
        raise FotoInvalida("La foto pesa más de 5 MB")
    if not contenido:
        raise FotoInvalida("El archivo está vacío")

    # No le creo a la extensión ni al content-type: miro lo que es de verdad
    try:
        img = Image.open(BytesIO(contenido))
        formato = img.format
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise FotoInvalida("No pudimos leer la foto. Subila en jpg, png o webp")
    if formato not in FORMATOS:
        raise FotoInvalida("La foto tiene que ser jpg, png o webp")

    # Las fotos del celu vienen giradas y la orientación va aparte (EXIF)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((LADO_MAX, LADO_MAX))  # solo achica, nunca agranda
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")

    salida = BytesIO()
    img.save(salida, "WEBP", quality=82)  # sin EXIF: no se filtra la ubicación del celu
    return salida.getvalue()


def guardar_foto_producto(contenido: bytes) -> str:
    return storage.guardar_archivo("productos", "webp", procesar(contenido))
