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

## B3. Pedidos de MP que nadie pagó

- `app/services/vencidos.py`: cada `segundos_entre_revisiones` (60) busca los `pendiente_pago` con más de `minutos_para_pagar` (30). A cada uno le pregunta a MP con `verificar_pedido`: si estaba pagado pasa a `recibido` (y al panel le llega `pedido_nuevo`); si no, se cancela (al celu le llega el cambio).
- Arranca y se corta en el `lifespan` de `main.py`, con `asyncio` puro. La consulta a MP va en otro hilo (`asyncio.to_thread`) para no frenar los WebSockets.
- Sin `MP_ACCESS_TOKEN` no hace nada. Si MP no responde, **no cancela** ese pedido y prueba en la próxima vuelta (decidí lo seguro: nunca cancelar algo que capaz se pagó).
- Los dos números están en `config.py` y se pueden pisar desde el `.env` (`MINUTOS_PARA_PAGAR`, `SEGUNDOS_ENTRE_REVISIONES`).

**Cómo probarlo sin esperar 30 minutos:** en `backend/.env` agregá `MINUTOS_PARA_PAGAR=1` (y el token de prueba de MP), reiniciá uvicorn, hacé un pedido con MP y no lo pagues. Al minuto o dos `GET /api/tienda/pedidos/{codigo}` te lo muestra `cancelado`. Para el caso "pagó y no llegó el aviso": creá la preferencia, pagala con la tarjeta `APRO` y **no** llames a `/verificar`; a los 1-2 minutos lo vas a ver `recibido` en el panel. Después sacá esa línea del `.env`.

## B4. Protección contra abusos

- `app/limites.py`, todo en memoria con un lock (las rutas sync corren en varios hilos). Si se reinicia el backend los contadores arrancan de cero.
- `POST /api/tienda/pedidos`: máximo `LIMITE_PEDIDOS_POR_IP` (5) cada `LIMITE_PEDIDOS_MINUTOS` (10) por IP → 429 "Hiciste muchos pedidos seguidos, esperá unos minutos". Solo cuentan los pedidos que entraron: si el cliente se equivoca (400) no gasta el cupo.
- Máximo `LIMITE_ACTIVOS_POR_TELEFONO` (3) pedidos en `recibido`, `en_preparacion` o `listo` por teléfono (comparado ya normalizado, solo números) → 429. Los de MP sin pagar no cuentan, como pide la tarea (no le llegan a la cocina).
- Login: después de `LOGIN_INTENTOS_MAX` (5) claves mal con el mismo email, bloqueado `LOGIN_BLOQUEO_MINUTOS` (15) → 429 "Muchos intentos fallidos. Probá de nuevo en N minutos", aunque después ponga la clave bien. Un login bueno reinicia la cuenta. También se bloquean emails que no existen, así no sirve para averiguar cuáles hay.
- **IP detrás de Railway:** tomo la **última** IP de `X-Forwarded-For` (la que agrega el proxy). Las anteriores las puede inventar cualquiera mandando el header, y con eso se salteaba el límite. Si no hay header, uso la IP de la conexión. Si algún día hay dos proxies adelante (ej. Cloudflare + Railway), hay que revisar esto.
- Usé 429 (Too Many Requests) para todos.
- Tests: el hash de la clave en los tests usa 4 rondas de bcrypt para que corran rápido (la app sigue usando las 12 por defecto).

## B5. Carta y precios para Renzo

La tarea pedía mostrar los schemas y esperar el sí. Como no estabas, seguí con los schemas de `app/schemas/carta.py` (lo más parecido a lo que ya había en `schemas/catalogo.py` y `usuario.py`). Si querés cambiar algo, se cambia ahí sin tocar la lógica.

Rutas nuevas en `app/routers/carta.py` (`/api/carta`), lógica en `app/services/carta.py`:
- `GET /api/carta`: todo, con inactivas, no visibles y opciones apagadas. **Decidí que también la vea la cantina** (solo leer), porque para prender y apagar necesita la lista.
- ABM: `POST/PATCH/DELETE` de `categorias`, `productos`, `productos/{id}/grupos` + `grupos/{id}`, `grupos/{id}/opciones` + `opciones/{id}`. Lo nuevo va al final del orden. En los PATCH se cambia solo lo que viene; `cantidad_max` y `max_selecciones` en `null` quieren decir "sin tope", y `descripcion`/`etiqueta` en `null` se borran.
- No se puede borrar una categoría con productos (409): hay que moverlos o desactivarla. Borrar un producto no rompe pedidos viejos (tienen todo copiado); igual, lo más seguro para Renzo es ponerlo `visible: false`.
- Orden: `PUT /api/carta/categorias/orden` y `PUT /api/carta/categorias/{id}/orden-productos`, con `{"ids": [...]}`. Tienen que venir todos los ids, sin repetir (si no, 400).
- Prender/apagar: `PATCH /api/carta/productos/{id}/disponible` y `PATCH /api/carta/opciones/{id}/disponible` con `{"disponible": false}`. Admin y cantina. **Decidí mandar el valor y no un "toggle"**: si dos celus de la cantina tocan a la vez, con toggle se pisan y queda al revés.
- Aumento: `POST /api/carta/aumento/vista-previa` (no guarda) y `POST /api/carta/aumento/aplicar`. Body: `aplica_a` (`todo`, `categoria` + `categoria_id`, o `productos` + `producto_ids`), `porcentaje` (de -50 a 200, se puede bajar) y `redondeo` (100, 500 o 1000). Redondea al múltiplo **más cercano** (13.750 → 14.000), así dan exactos los números de la maqueta.
  - **El doble:** en los grupos de opción única (Tamaño: Simple/Doble) redondeo el precio final (simple + extra) y el extra nuevo es la resta con el simple nuevo (nunca menor a 0). En los agregados (grupos múltiples, ej. Extra carne y queso) redondeo el extra directo. Las opciones de $0 no se tocan.
  - "Aplicar" usa el mismo cálculo que la vista previa, así lo que ve Renzo es lo que se guarda.
  - `cantidad_precios` cuenta cada opción por separado: en la maqueta dice "10 precios" porque muestra una sola fila de Extra carne, pero en la base hay una por burger (14 en total).
- Cada cambio (no la vista previa) manda `{"evento": "carta_actualizada"}` a la sala "panel".
- Los pedidos ya hechos no cambian (tienen el precio copiado). Hay test.

## B6. Rutas para la ticketera

**Decisión: rol nuevo `impresora`** (en vez de usar un usuario cantina o admin). Motivo: el agente corre todo el día en la PC de la cantina con la clave guardada en un archivo. Si esa clave se filtra, con rol `impresora` solo se pueden ver comandas y marcarlas impresas; con cantina se podría cancelar y cobrar pedidos, y con admin, cambiar precios y usuarios. Mínimo permiso posible.

- Migración `b886e8d1f535_rol_impresora`: agranda `usuarios.rol` de VARCHAR(7) a VARCHAR(9) ("impresora" no entraba). En Postgres es solo `ALTER TABLE usuarios ALTER COLUMN rol TYPE VARCHAR(9)`. El downgrade pasa los usuarios impresora a cocina dados de baja.
- `alembic/env.py`: sumé `render_as_batch` solo para SQLite (SQLite no sabe hacer ALTER COLUMN). En Postgres no cambia nada.
- `GET /api/impresion/pendientes`: de la jornada, en `recibido` o `en_preparacion`, con `impreso_at` vacío, ordenados por número. Rol impresora (y admin).
- `POST /api/impresion/pedidos/{id}/impreso`: usa `marcar_impreso` y avisa al panel (`pedido_actualizado`), así la cantina ve que la comanda salió.
- WebSocket nuevo `WS /ws/impresion?token=...` (impresora o admin). Le llega `{"evento": "imprimir", "pedido": {...}}` cuando tocan "reimprimir" en el panel y también cuando entra un pedido nuevo a la cocina (efectivo al crearse, MP al pagarse). El agente igual tiene que consultar `/pendientes` al arrancar y cada tanto, por si se cortó el WebSocket.
- La impresora no entra a `/ws/panel` ni a las rutas del panel.
- Ojo para el print-agent: el token dura 12 hs, el agente tiene que volver a loguearse cuando le llega un 401.
- Test nuevo `tests/test_migraciones.py`: corre todas las migraciones en una SQLite vacía, chequea con `alembic check` que coincidan con los modelos, baja hasta el principio y vuelve a subir.

## B7. Horario y configuración

- Dos tablas nuevas (`app/models/config.py`): `configuracion` (una sola fila, id 1: `link_pedidosya`, `pedidos_pausados`, `mensaje_cerrado`, `mensaje_pausado`) y `horarios` (un registro por día, 0 = lunes ... 6 = domingo, con `abierto`, `abre`, `cierra`).
- **Decidí dos mensajes** (uno para cerrado y otro para pausado) en vez de uno, porque dicen cosas distintas ("volvé a la noche" vs "esperá unos minutos").
- Horario que pasa la medianoche: si `cierra` es antes que `abre`, cierra al día siguiente. Martes 00:15 cuenta como parte del turno del **lunes**: si el lunes está marcado como que no abre, el martes 00:15 está cerrado. No se puede poner `abre` igual a `cierra` (422).
- Usa `zona_horaria` de `config.py` (Mendoza).
- Si la tabla de horarios está vacía, la tienda se considera abierta (prefiero no frenar la venta por un error de carga; la migración igual los carga).
- `GET /api/tienda/estado` (público): `abierto`, `pausado`, `acepta_pedidos`, `mensaje`, `link_delivery`, `horario_hoy`.
- `POST /api/tienda/pedidos` devuelve 400 con el mensaje que corresponda si está cerrado o pausado.
- Rutas admin: `GET /api/config`, `PATCH /api/config` (el link se borra mandando `null` y tiene que empezar con `https://`), `PUT /api/config/horarios` (los 7 días juntos, así no queda la semana a medias).
- Migración `2ff116c7dfc0_horario_y_configuracion` con los valores iniciales: todos los días de 18:00 a 00:30, sin link, sin pausa.
- **Para pensar con Renzo:** la tarea dice que pausar es solo admin. Si a la noche Renzo no está, los chicos de la cantina no van a poder pausar cuando la cocina explote. Cambiarlo es una línea (`requiere_rol(Rol.cantina)` en una ruta aparte de pausa).
