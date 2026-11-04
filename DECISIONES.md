# Decisiones de la Tarea 1 (backend)

Todo se hizo en la rama `backend-pendientes`. Main no se tocó, no se hizo push ni deploy, no se tocó el `.env` ni la base de Docker.

## Tests de lo que ya andaba (antes de B1)

- Tests con pytest en `backend/tests/`, contra SQLite en memoria. Las variables de entorno se pisan en `tests/conftest.py` antes de importar la app, así no leen el `.env` (y nunca usan el token de MP real).
- La carta de los tests es la del seed (`armar_carta()`), así los precios son los reales de BRUTO.
- **Cambio chico en el backend:** `inicio_jornada()` ahora devuelve la hora en UTC (la misma hora, otra zona). En Postgres no cambia nada, pero SQLite compara fechas como texto y la numeración del día se corría 3 horas. Sin esto no se podía testear bien.
- `pytest` y `httpx` quedaron en `backend/requirements.txt` (la tarea pide un solo requirements).

## B1. Arreglos de la revisión

1. `avisar_pedido` (app/ws.py) no le manda nada a la sala "panel" si el pedido está en `pendiente_pago`; al celu sí. El evento `pedido_nuevo` al aprobarse MP lo pasa quien llama (`avisar_pedido(id, "pedido_nuevo")`, ver B2). En `GET /api/panel/pedidos` la cocina nunca ve `pendiente_pago` (ni con `?todos=true` ni con `?estado=pendiente_pago`); cantina y admin sí.
   - Detalle: si la cantina cancela un pedido de MP sin pagar, al panel le llega un `pedido_actualizado` de un pedido que nunca vio como nuevo (ya está cancelado). El front lo tiene que ignorar si no lo tiene en la lista.
2. Borré el `requirements.txt` de la raíz. Queda solo `backend/requirements.txt`.
3. `config.py` busca el `.env` en `backend/` usando la ruta del archivo (`ENV_FILE`), se corra desde donde se corra.
4. Pedido en efectivo sin cobrar no pasa a `entregado` (400 "Cobralo antes de marcarlo entregado"). Nueva ruta `POST /api/panel/pedidos/{id}/cobrar-y-entregar` (cantina/admin): solo efectivo, solo desde `listo`; si ya estaba cobrado, solo entrega. Valida todo antes de tocar nada.
5. Cancelar un pedido de MP ya pagado: solo admin (403 para cantina). La respuesta de `PATCH .../estado` ahora trae un campo `aviso` (null casi siempre) que en ese caso dice "Acordate de devolver el pago desde Mercado Pago". Decidí un campo en el JSON y no un header porque el front lo lee más fácil.

**Cómo probar B1 en /docs:** loguearse con Authorize (admin), hacer un pedido en efectivo y uno con MP desde `POST /api/tienda/pedidos`. (1) Con `python -m scripts.escuchar_panel` abierto, el de MP no aparece; con un usuario cocina, `GET /api/panel/pedidos?todos=true` no lo muestra. (4) Pasar el de efectivo a `en_preparacion` → `listo` → `entregado`: da 400; después `POST .../cobrar-y-entregar` lo deja entregado y cobrado. (5) Para MP pagado hace falta B2 (o cambiar `estado_pago` a mano en la base): con cantina da 403, con admin da 200 y el `aviso`.

## B2. Mercado Pago

Estaban los dos archivos de `docs/mercadopago/`. Los copié a `app/services/pagos.py` y `app/routers/pagos.py` y sumé el router en `main.py`. `mercadopago` ya estaba en `requirements.txt`.

**Lo que chocaba con B1 y cómo lo resolví:**
- El router avisaba siempre `pedido_actualizado` al aprobarse un pago. Ahora usa `evento_para_el_panel(pedido)`: si el pedido quedó `recibido` y aprobado (o sea, recién pagado) manda `pedido_nuevo`; si no, `pedido_actualizado`. Un pago rechazado deja el pedido en `pendiente_pago`, así que por B1 no le llega al panel, solo al celu.
- `MINUTOS_PARA_PAGAR = 30` estaba fijo en el service. Lo pasé a `config.py` (`minutos_para_pagar`) porque B3 usa el mismo número para cancelar. El link de MP vence a la misma hora en que se cancela el pedido.
- Sumé un log de error si pagan un pedido que ya estaba cancelado (queda cancelado y con pago aprobado: hay que devolver la plata). Antes pasaba en silencio.

**Cosas a tener en cuenta (no las cambié):**
- Si MP cobra un monto distinto al del pedido, `aplicar_pago` no lo aprueba y solo deja un log. El pedido sigue en `pendiente_pago` y B3 lo va a cancelar a los 30 min aunque haya plata cobrada. No debería pasar nunca (el monto sale de nuestra preferencia), pero si pasa hay que revisarlo a mano en MP.
- El link de sandbox se usa solo si el token empieza con `TEST-`. Las credenciales de prueba nuevas de MP (las de un usuario de prueba vendedor) empiezan con `APP_USR-`; en ese caso se usa `init_point`, que con usuarios de prueba igual es sandbox. Anda en los dos casos.

**Cómo probarlo con credenciales de prueba de MP:**
1. En https://www.mercadopago.com.ar/developers → Tus integraciones → creá una aplicación (Checkout Pro). En "Cuentas de prueba" creá un usuario **vendedor** y uno **comprador**.
2. Entrá a developers con el usuario vendedor de prueba y copiá su Access Token (o usá las "Credenciales de prueba" de tu app). En `backend/.env` poné `MP_ACCESS_TOKEN=` con ese token. `MP_WEBHOOK_SECRET` dejalo vacío en tu compu (sin https el webhook no llega igual). Reiniciá uvicorn.
3. En /docs: `POST /api/tienda/pedidos` con `"metodo_pago": "mercadopago"` → copiá el `codigo`. `POST /api/pagos/{codigo}/preferencia` → abrí `link_pago` en una ventana de incógnito y entrá con el usuario **comprador** de prueba.
4. Tarjeta de prueba: Mastercard `5031 7557 3453 0604` o Visa `4509 9535 6623 3704`, CVV `123`, vencimiento `11/30`, DNI `12345678`. En "Nombre del titular" poné `APRO` para que se apruebe u `OTHE` para que se rechace.
5. Volvé a /docs: `POST /api/pagos/{codigo}/verificar` → tiene que quedar `recibido` y `aprobado`. Con `python -m scripts.escuchar_panel` abierto vas a ver el `[pedido_nuevo]` recién ahí.
