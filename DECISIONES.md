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
