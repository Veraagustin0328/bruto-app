# Agente de la ticketera

Corre en la PC de la cantina e imprime las comandas solo. Por ahora la "impresora" es la consola y el archivo `comandas.txt` (48 caracteres de ancho, papel de 80 mm). Cuando tengamos la ticketera se cambia solo `imprimir()` en `impresora.py` (ahí hay un ejemplo con python-escpos).

## Cómo levantarlo (PowerShell)

1. Crear un usuario de rol `impresora` (lo hace el admin en http://localhost:8001/docs con `POST /api/auth/usuarios`).
2. Configurarlo:

```powershell
cd C:\Users\veraa\bruto-app\print-agent
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.ejemplo.env config.env   # y completá email y contraseña
python agente.py
```

`python agente.py --una-vez` imprime lo pendiente y termina (sirve para probar).

## Qué hace

- Al arrancar imprime lo que haya quedado sin imprimir (`GET /api/impresion/pendientes`).
- Escucha `WS /ws/impresion`: le llegan los pedidos nuevos y los "Reimprimir" del panel.
- Cada minuto vuelve a pedir los pendientes, por si se cortó el WebSocket.
- Después de imprimir avisa al backend (`POST /api/impresion/pedidos/{id}/impreso`), así no sale dos veces.
- Si el token vence (dura 12 hs) se loguea de nuevo solo. Si se corta internet, reintenta solo.
