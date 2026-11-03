"""
Se conecta al WebSocket del panel y muestra en la terminal cada pedido
que entra o cambia. Sirve para probar el tiempo real sin tener el front.

Uso (con uvicorn corriendo, en otra terminal con el venv activado):
    python -m scripts.escuchar_panel
"""
import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from getpass import getpass

import websockets

API = "http://localhost:8001"
WS = "ws://localhost:8001"


def loguearse() -> str:
    email = input("Email: ").strip()
    password = getpass("Contraseña (no se ve mientras escribís): ")
    datos = urllib.parse.urlencode({"username": email, "password": password}).encode()
    with urllib.request.urlopen(f"{API}/api/auth/login", data=datos) as r:
        return json.load(r)["access_token"]


def mostrar(mensaje: dict):
    p = mensaje["pedido"]
    donde = p["ubicacion"] or "take away"
    items = ", ".join(f"{i['cantidad']}x {i['nombre_producto']}" for i in p["items"])
    print(
        f"[{mensaje['evento']}] #{p['numero']:03d} · {p['estado']} · pago {p['estado_pago']}"
        f" · {donde} · {p['nombre']} {p['apellido']} · {items} · ${p['total']:,.0f}".replace(",", ".")
    )


async def escuchar(token: str):
    async with websockets.connect(f"{WS}/ws/panel?token={token}") as ws:
        print("Conectado. Hacé un pedido o cambiá un estado en /docs y miralo acá. Ctrl + C para salir.\n")
        while True:
            texto = await ws.recv()
            if texto != "pong":
                mostrar(json.loads(texto))


if __name__ == "__main__":
    try:
        asyncio.run(escuchar(loguearse()))
    except KeyboardInterrupt:
        print("\nChau.")
    except urllib.error.HTTPError:
        print("Email o contraseña incorrectos.")
