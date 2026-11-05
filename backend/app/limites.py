"""
Límites contra abusos: pedidos falsos y gente probando claves.

Todo en memoria del proceso, sin Redis. Con un solo uvicorn (lo que usa BRUTO)
alcanza. Si se reinicia el backend, los contadores arrancan de cero: no pasa nada.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.config import settings


def reloj() -> float:
    # Aparte así los tests lo pueden adelantar sin tocar el reloj de todo Python
    return time.monotonic()


class Ventana:
    """Cuenta eventos por clave en los últimos N segundos."""

    def __init__(self):
        self.eventos: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()  # las rutas sync corren en varios hilos

    def _limpiar(self, clave: str, segundos: float, ahora: float):
        cola = self.eventos[clave]
        while cola and cola[0] <= ahora - segundos:
            cola.popleft()
        if not cola:
            del self.eventos[clave]

    def cuantos(self, clave: str, segundos: float, ahora: float | None = None) -> int:
        ahora = reloj() if ahora is None else ahora
        with self.lock:
            self._limpiar(clave, segundos, ahora)
            return len(self.eventos.get(clave, ()))

    def sumar(self, clave: str, ahora: float | None = None):
        ahora = reloj() if ahora is None else ahora
        with self.lock:
            self.eventos[clave].append(ahora)

    def borrar(self, clave: str):
        with self.lock:
            self.eventos.pop(clave, None)

    def reiniciar(self):
        with self.lock:
            self.eventos.clear()


pedidos_por_ip = Ventana()
logins_fallidos = Ventana()
bloqueados: dict[str, float] = {}  # email -> hasta cuándo (según reloj())
_lock_bloqueos = threading.Lock()


def reiniciar():
    # Para los tests
    pedidos_por_ip.reiniciar()
    logins_fallidos.reiniciar()
    with _lock_bloqueos:
        bloqueados.clear()


def ip_del_cliente(request: Request) -> str:
    # En Railway estamos detrás de un proxy: la IP real viene en X-Forwarded-For.
    # Tomo la ÚLTIMA de la lista, que es la que agregó el proxy. Las de antes
    # las puede inventar cualquiera mandando el header a mano
    reenviado = request.headers.get("x-forwarded-for")
    if reenviado:
        ultima = reenviado.split(",")[-1].strip()
        if ultima:
            return ultima
    return request.client.host if request.client else "desconocida"


# ---------- pedidos ----------


def puede_pedir(ip: str) -> bool:
    segundos = settings.limite_pedidos_minutos * 60
    return pedidos_por_ip.cuantos(ip, segundos) < settings.limite_pedidos_por_ip


def anotar_pedido(ip: str):
    pedidos_por_ip.sumar(ip)


# ---------- login ----------


def segundos_de_bloqueo(email: str) -> float:
    # Cuánto le falta a este email para poder volver a probar. 0 = puede
    with _lock_bloqueos:
        hasta = bloqueados.get(email)
        if hasta is None:
            return 0
        falta = hasta - reloj()
        if falta <= 0:
            del bloqueados[email]
            return 0
        return falta


def anotar_login_fallido(email: str):
    minutos = settings.login_bloqueo_minutos
    logins_fallidos.sumar(email)
    if logins_fallidos.cuantos(email, minutos * 60) >= settings.login_intentos_max:
        with _lock_bloqueos:
            bloqueados[email] = reloj() + minutos * 60
        logins_fallidos.borrar(email)


def anotar_login_ok(email: str):
    logins_fallidos.borrar(email)
