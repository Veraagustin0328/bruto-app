"""
Agente de la ticketera de BRUTO. Corre en la PC de la cantina.

- Entra con un usuario de rol "impresora" (ver DECISIONES.md, paso B6)
- Al arrancar imprime lo que haya quedado pendiente (por si se cortó internet)
- Escucha /ws/impresion: le llegan los pedidos nuevos y los "reimprimir" del panel
- Cada minuto, por las dudas, vuelve a pedir los pendientes
- Después de imprimir cada comanda le avisa al backend (así no sale dos veces)

Uso (PowerShell, desde la carpeta print-agent):
    python agente.py             # queda corriendo
    python agente.py --una-vez   # imprime los pendientes y termina
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx
import websockets

from comanda import armar_comanda
from impresora import imprimir

AQUI = Path(__file__).resolve().parent
log = logging.getLogger("ticketera")

REVISAR_CADA_S = 60
PING_CADA_S = 25


def leer_config() -> dict:
    # config.env (que no se sube a git) y las variables de entorno, que mandan
    datos = {}
    archivo = AQUI / "config.env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                datos[clave.strip()] = valor.strip()
    for clave in ("BRUTO_API_URL", "BRUTO_EMAIL", "BRUTO_PASSWORD"):
        if os.environ.get(clave):
            datos[clave] = os.environ[clave]
    faltan = [c for c in ("BRUTO_EMAIL", "BRUTO_PASSWORD") if not datos.get(c)]
    if faltan:
        sys.exit(f"Falta {', '.join(faltan)}. Copiá config.ejemplo.env como config.env y completalo.")
    datos.setdefault("BRUTO_API_URL", "http://localhost:8001")
    datos["BRUTO_API_URL"] = datos["BRUTO_API_URL"].rstrip("/")
    return datos


class SinSesion(Exception):
    """El token venció o no sirve: hay que loguearse de nuevo."""


class Agente:
    def __init__(self, config: dict):
        self.api = config["BRUTO_API_URL"]
        self.email = config["BRUTO_EMAIL"]
        self.password = config["BRUTO_PASSWORD"]
        self.token: str | None = None
        self.http = httpx.AsyncClient(timeout=15)
        self.lock = asyncio.Lock()
        # (id, updated_at) de lo que ya imprimí: si el mismo pedido llega por el
        # WebSocket y por la consulta a la vez, sale una sola vez. Un "reimprimir"
        # cambia el updated_at, así que ese sí sale de nuevo
        self.ya_impresos: dict[tuple, float] = {}

    # ---------- backend ----------

    async def login(self):
        r = await self.http.post(
            f"{self.api}/api/auth/login", data={"username": self.email, "password": self.password}
        )
        if r.status_code != 200:
            detalle = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
            raise RuntimeError(f"No pude entrar como {self.email}: {detalle}")
        datos = r.json()
        if datos["usuario"]["rol"] not in ("impresora", "admin"):
            raise RuntimeError("El usuario tiene que ser de rol impresora")
        self.token = datos["access_token"]
        log.info("Logueado como %s", self.email)

    async def pedir(self, metodo: str, ruta: str):
        if not self.token:
            await self.login()
        r = await self.http.request(metodo, f"{self.api}{ruta}", headers={"Authorization": f"Bearer {self.token}"})
        if r.status_code == 401:
            # El token dura 12 hs: me logueo de nuevo y reintento una vez
            await self.login()
            r = await self.http.request(metodo, f"{self.api}{ruta}", headers={"Authorization": f"Bearer {self.token}"})
        r.raise_for_status()
        return r.json()

    # ---------- imprimir ----------

    async def imprimir_pedido(self, pedido: dict):
        clave = (pedido["id"], pedido.get("updated_at"))
        async with self.lock:
            if clave in self.ya_impresos:
                return
            if pedido["estado"] not in ("recibido", "en_preparacion"):
                return
            imprimir(armar_comanda(pedido))
            self.ya_impresos[clave] = time.time()
            # Me olvido de lo viejo para que no crezca para siempre
            hace_rato = time.time() - 3600
            self.ya_impresos = {k: v for k, v in self.ya_impresos.items() if v > hace_rato}
        try:
            await self.pedir("POST", f"/api/impresion/pedidos/{pedido['id']}/impreso")
            log.info("Comanda #%03d impresa", pedido["numero"])
        except Exception as e:  # noqa: BLE001
            # Salió por la ticketera pero no pude avisar: en la próxima vuelta puede salir de nuevo
            log.warning("Imprimí la #%03d pero no pude marcarla: %s", pedido["numero"], e)

    async def imprimir_pendientes(self):
        pendientes = await self.pedir("GET", "/api/impresion/pendientes")
        if pendientes:
            log.info("%d comanda(s) pendiente(s)", len(pendientes))
        for pedido in pendientes:
            await self.imprimir_pedido(pedido)

    # ---------- loops ----------

    async def revisar_cada_tanto(self):
        while True:
            await asyncio.sleep(REVISAR_CADA_S)
            try:
                await self.imprimir_pendientes()
            except Exception as e:  # noqa: BLE001
                log.warning("No pude revisar los pendientes: %s", e)

    async def escuchar(self):
        espera = 1
        while True:
            try:
                if not self.token:
                    await self.login()
                url = self.api.replace("http", "ws", 1) + f"/ws/impresion?token={self.token}"
                async with websockets.connect(url, ping_interval=None) as ws:
                    log.info("Conectado, esperando comandas")
                    espera = 1
                    # Por si entró algo mientras estaba desconectado
                    await self.imprimir_pendientes()
                    ping = asyncio.create_task(self.pinguear(ws))
                    try:
                        async for mensaje in ws:
                            if mensaje == "pong":
                                continue
                            datos = json.loads(mensaje)
                            if datos.get("evento") == "imprimir" and datos.get("pedido"):
                                await self.imprimir_pedido(datos["pedido"])
                    finally:
                        ping.cancel()
            except websockets.exceptions.ConnectionClosedError as e:
                if e.rcvd and e.rcvd.code == 1008:
                    log.warning("El backend no aceptó el token, me logueo de nuevo")
                    self.token = None
                else:
                    log.warning("Se cortó la conexión: %s", e)
            except websockets.exceptions.InvalidStatus as e:
                # El backend cierra antes de aceptar si el token no sirve: llega como 403
                log.warning("El backend rechazó la conexión (%s), me logueo de nuevo", e.response.status_code)
                self.token = None
            except (OSError, httpx.HTTPError, websockets.exceptions.WebSocketException) as e:
                log.warning("Sin conexión con el backend (%s). Reintento en %d s", e, espera)
            except RuntimeError as e:
                log.error("%s. Reintento en %d s", e, espera)
            await asyncio.sleep(espera)
            espera = min(espera * 2, 30)

    async def pinguear(self, ws):
        while True:
            await asyncio.sleep(PING_CADA_S)
            await ws.send("ping")


async def main():
    parser = argparse.ArgumentParser(description="Agente de la ticketera de BRUTO")
    parser.add_argument("--una-vez", action="store_true", help="imprime los pendientes y termina")
    args = parser.parse_args()

    agente = Agente(leer_config())
    try:
        if args.una_vez:
            await agente.imprimir_pendientes()
            return
        await asyncio.gather(agente.escuchar(), agente.revisar_cada_tanto())
    finally:
        await agente.http.aclose()


if __name__ == "__main__":
    # La consola de Windows a veces no conoce algunos caracteres (█, ✂): que no explote
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Chau.")
