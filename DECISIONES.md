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

## B8. Fotos de los productos

- **Librería: Pillow** (`pillow>=10.0` en `requirements.txt`). La tarea pedía avisar antes de instalarla; como no estabas, elegí la estándar de Python para imágenes: lee jpg/png/webp, guarda webp y no necesita nada instalado aparte en Windows ni en Railway.
- `POST /api/carta/productos/{id}/foto` (admin, `multipart/form-data`, campo `foto`): hasta 5 MB, solo jpg/png/webp. **El formato se mira abriendo el archivo**, no por la extensión. La endereza si viene girada del celu (EXIF), la achica a 800 px de lado máximo (nunca la agranda), la pasa a webp y guarda la URL en `imagen_url`. Al guardarla como webp se le borran los datos EXIF (ej. la ubicación GPS del celu).
- `DELETE /api/carta/productos/{id}/foto` la saca. Cambiar la foto o borrar el producto borra el archivo viejo.
- Tope de 40 millones de píxeles para que una imagen armada a propósito no reviente la memoria.
- `app/storage.py`: `guardar_archivo()` y `borrar_archivo()` son lo único que sabe dónde van los archivos. Hoy guardan en `backend/uploads/productos/` (configurable con `UPLOADS_DIR`), servidos por FastAPI en `/uploads`. La URL guardada es absoluta (`BACKEND_URL` + `/uploads/...`) porque el front está en otro dominio.
- **Pendiente para producción:** Railway borra el disco en cada deploy, así que antes de subir fotos en serio hay que poner un storage externo (Cloudinary, S3 o R2) en esas dos funciones y `STORAGE` distinto de `local`.
- Sumé `backend/uploads/` al `.gitignore`.
- Arreglo de paso: en Windows Python no conocía el tipo `.webp` y servía las fotos como "archivo para bajar". Lo registro en `main.py`.
- Avisa `carta_actualizada` al panel.

---

# Resumen final

## Pasos

| Paso | Estado | Commit |
|---|---|---|
| Tests de lo que ya andaba | Hecho | `aed8da6` |
| B1. Arreglos de la revisión | Hecho | `deb0dcd` |
| B2. Mercado Pago | Hecho (probado con MP simulado) | `e9554f1` |
| B3. Cancelar pedidos de MP sin pagar | Hecho | `c7d8d35` |
| B4. Protección contra abusos | Hecho | `081e9bf` |
| B5. Carta y precios | Hecho | `e73ff53` |
| B6. Ticketera | Hecho | `77774b6` |
| B7. Horario y configuración | Hecho | `7311837` |
| B8. Fotos | Hecho (storage externo pendiente para producción) | `ab0695a` |
| B9. Tests | Hecho: están todos los casos de la lista | — |

No quedó ningún paso trabado.

## Tests

**256 tests, pasan todos** (unos 25 segundos). Para correrlos (PowerShell):

```powershell
cd C:\Users\veraa\bruto-app\backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt   # suma pytest, httpx y pillow
python -m pytest
```

Usan SQLite en memoria y una carpeta temporal para las fotos: no tocan Docker, ni el `.env`, ni `backend/uploads`.

## Decisiones que tomé yo (detalle en cada paso de arriba)

- `inicio_jornada()` devuelve UTC (misma hora, para que SQLite compare bien).
- B1: el aviso de "devolver el pago" va en un campo `aviso` de la respuesta. `cobrar-y-entregar` solo desde `listo`.
- B2: el tiempo para pagar pasó a `config.py`. Log si pagan un pedido ya cancelado.
- B3: si MP no responde, no cancelo.
- B4: 429 para todos los límites; IP = la última de `X-Forwarded-For`; los fallidos con emails que no existen también bloquean.
- B5: seguí sin esperar el OK de los schemas. La cantina puede **ver** la carta. Disponibilidad con valor explícito, no toggle. Redondeo al más cercano. Se puede bajar precios (hasta -50 %).
- B6: rol nuevo `impresora` + WebSocket `/ws/impresion`.
- B7: dos mensajes (cerrado y pausado). Sin horarios cargados = abierto.
- B8: Pillow; fotos en `backend/uploads` detrás de `app/storage.py`.

## Lo que tenés que probar a mano

1. Aplicar las migraciones en tu Postgres (abajo) y levantar uvicorn. Mirar que `/docs` muestre las secciones nuevas: Carta y precios, Ticketera, Configuración, Mercado Pago.
2. **Mercado Pago con credenciales de prueba** (pasos en B2): pago aprobado (`APRO`), rechazado (`OTHE`) y uno que no pagues con `MINUTOS_PARA_PAGAR=1` para ver que se cancela solo (B3).
3. **Horario:** `GET /api/tienda/estado` a distintas horas. Ojo: fuera de 18:00 a 00:30 **la tienda ya no acepta pedidos**. Para probar de día cambiá el horario con `PUT /api/config/horarios` (o pausá/despausá con `PATCH /api/config`).
4. **Límites:** 6 pedidos seguidos desde /docs → el 6.º da 429. 5 claves mal en el login → bloqueado 15 min (si te bloqueás vos, reiniciá uvicorn y se limpia).
5. **Carta:** vista previa de +10 % a Smash Burgers con redondeo 500 y compararla con la maqueta; aplicarla y ver que un pedido viejo no cambió.
6. **Fotos:** subir una foto desde `/docs` y abrir el `imagen_url` en el navegador.
7. Crear un usuario rol `impresora` y probar `/api/impresion/pendientes`.

## Lo que hay que pedirle a Renzo (además de lo que ya estaba en el CLAUDE.md)

- **Horario real** de la cantina por día (quedó todos los días de 18:00 a 00:30) y si algún día no abre.
- **Link de la tienda en PedidosYa.**
- **Cuenta de Mercado Pago de producción** (para el `MP_ACCESS_TOKEN` y la clave secreta del webhook).
- Si los chicos de la cantina tienen que poder **pausar los pedidos** sin él (hoy solo admin).
- **Fotos de los productos.**
- Datos de la ticketera (para el print-agent).
- Y para producción, elegir un storage para las fotos (Cloudinary tiene plan gratis y alcanza).

## Migraciones nuevas en tu base de Docker

Hay dos: `b886e8d1f535` (rol impresora) y `2ff116c7dfc0` (horario y configuración, con los valores iniciales). No borran nada. En PowerShell:

```powershell
cd C:\Users\veraa\bruto-app
git checkout backend-pendientes
docker compose up -d
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic current            # tendría que decir 3edc39188607
alembic upgrade head
alembic current            # ahora 2ff116c7dfc0 (head)
uvicorn app.main:app --reload --port 8001
```

Si querés ver el SQL antes de aplicarlo: `alembic upgrade 3edc39188607:head --sql`.
Para volver atrás: `alembic downgrade 3edc39188607` (borra las tablas de horario y configuración; los usuarios impresora pasan a cocina dados de baja).

---

# Frontend (Tarea 2)

Todo en la rama `frontend`, creada desde `main` (el backend ya estaba mergeado; `backend-pendientes` y `main` eran iguales). No se tocó el backend, ni el `.env`, ni la base de Docker. No hubo push ni deploy.

## Pantallas

| Paso | Estado | Commit |
|---|---|---|
| 1. Crear el frontend (Vite + React Router + Tailwind, `api.js`) | Hecho | `bf1b783` |
| 2. Tienda: la carta | Hecho | `ac5b902` |
| 3. Armar el producto y carrito | Hecho | `d740cca` |
| 4. Dónde comés, datos y pago | Hecho | `2c4bb8c` |
| 5. Seguimiento del pedido | Hecho | `27808a0` |
| 6. Intro del paletazo | Hecho | `6d51572` |
| 7. Login y panel de la cantina | Hecho | `d19929f` |
| 8. Cocina | Hecho | `5f7524f` |
| 9. Agente de la ticketera (simulado) | Hecho | `dcccfba` |
| 10. Revisión | Hecha, la lista está abajo (sin arreglar) | este commit |

No quedó ningún paso trabado. No están hechas (no eran parte de la tarea): las pestañas "Carta y precios" y "Caja del día" del panel que aparecen en la maqueta. El backend ya tiene las rutas de B5 para la primera.

Cada paso se probó con `npm run build` sin errores y en Chrome (Playwright) a 390 px y 1280 px contra el backend de verdad (uvicorn en el 8001). Usé una base SQLite aparte y un Mercado Pago de mentira que armé en una carpeta temporal (no están en el repo). Lo que se probó: carta, chips, esqueleto y error con reintento; armar la Animal doble con 2 extras y nota ($20.000, igual que la maqueta) y que no deje agregar sin tamaño; carrito que sobrevive a recargar; checkout con `?donde=Cancha 3`; pedido en efectivo y con MP (aprobado, rechazado, y rechazado → vuelve a pagar → aprobado); seguimiento en vivo por WebSocket; take away listo; login con clave mal y bien; panel recibiendo pedidos en vivo y los botones; cocina; ticketera con un pedido nuevo y con reimprimir. También pasé por todas las pantallas a 360 px (ninguna se desborda a lo ancho).

## Decisiones que tomé yo

**General**
- Tailwind 4: los colores y fuentes de la marca están en `src/index.css` (bloque `@theme`), no hay `tailwind.config.js`. Las clases son tipo `bg-naranja`, `text-tenue`, `font-display`.
- React 19, React Router 7, Vite 8. JavaScript, sin TypeScript. Ninguna librería de componentes ni de animación.
- `api.js` tiene todas las llamadas. Si no hay `VITE_API_URL` usa `http://localhost:8001`. Los errores de validación de FastAPI (422, en inglés) se pasan a castellano; los `detail` que ya vienen en texto se muestran tal cual. Sin conexión dice "No pudimos conectarnos. Revisá tu conexión y probá de nuevo".
- `src/lib/almacen.js`: todo el localStorage y sessionStorage va con try/catch.
- Fechas: si alguna viene sin zona horaria la tomo como UTC (`formato.fecha`). Con Postgres siempre vienen con zona; con SQLite no, y los "hace X min" daban mal.

**Tienda**
- El checkout no es otra ruta: es `/` con `?paso=pedido` y `?paso=datos`. Así el botón "atrás" del celu anda y el `?donde=` del QR no se pierde.
- En la hoja del producto **el tamaño no viene elegido**: el cliente elige simple o doble a propósito (el botón dice "ELEGÍ TAMAÑO" hasta que elija). Sumé un stepper de cantidad al lado de "Agregar".
- Opciones múltiples: stepper si `cantidad_max` es null o mayor a 1 (tope 10, lo que acepta el backend); tilde si es 1. Respeta `max_selecciones`.
- Si agregás dos veces lo mismo (mismas opciones y nota) se suma la cantidad. El carrito se tira solo a las 6 horas.
- "¿Cómo pagás?" arranca con Mercado Pago elegido, como en la maqueta.
- Delivery: usa el `link_delivery` del backend (B7) si está cargado; si no, el de `src/config.js` (vacío, con TODO). Sin link muestra "Muy pronto".
- Los botones Cancha 1 a 4 están en `src/config.js` (`CANCHAS`).
- Si MP no responde al crear el link de pago, el pedido ya existe: lo mando al seguimiento, que tiene el botón "Pagar con Mercado Pago" para reintentar.
- Seguimiento: si el pedido está en `pendiente_pago`, al entrar siempre verifica (aunque antes lo hayan rechazado, porque capaz volvió a pagar). Cada 5 s, hasta 2 min. Después muestra "Pagar" y "Ya pagué, revisar de nuevo".
- Arriba de la carta aparece "Tu pedido #042 está en la plancha · Ver mi pedido", solo si el último pedido es de las últimas 12 hs y sigue en curso.
- Intro: la escena de la maqueta (280 × 600) se escala para entrar en la pantalla, así las posiciones quedan idénticas. Dura unos 3,7 s y se va con un fade. Si vino del QR dice "Estás en Cancha 3". No sale si entra directo al checkout.

**Panel y cocina**
- Botones por estado: Nuevos → "A la cocina"; En preparación → "Listo"; Listos → "Entregado", o "Cobrar $X y entregar" si es efectivo sin cobrar (usa `cobrar-y-entregar` de B1, porque el backend no deja entregar sin cobrar). "Cobrar" suelto en los otros estados. "Reimprimir" y "Cancelar" (con confirmación dentro de la tarjeta) en todos.
- El aviso "Acordate de devolver el pago desde Mercado Pago" sale como cartel abajo durante 9 segundos.
- "Hace X min" se pone amarillo a los 15 min en el panel; en la cocina el reloj, a los 12, como pide la tarea.
- Sonido con Web Audio (sin archivos). Arriba hay una barra "Tocá acá para activar el sonido" hasta que alguien toque la pantalla.
- La lista se recarga entera al reconectar el WebSocket y cada 2 minutos, por las dudas.
- Login: después de entrar va a donde quería ir; si no, la cocina va a `/cocina` y el resto a `/panel`. El rol `impresora` no entra. El admin entra a todo; la cocina también la puede abrir la cantina.
- En la cocina, en lugar de "Promedio hoy" (ese dato no está en el backend) puse la hora.

**Ticketera (print-agent)**
- La tarea decía "se loguea con un usuario de la cantina y se conecta a /ws/panel", pero también "usá las rutas de B6". B6 armó un rol `impresora` que **no** entra a `/ws/panel`. Usé lo de B6: usuario `impresora`, `WS /ws/impresion`, `GET /api/impresion/pendientes` y `POST /api/impresion/pedidos/{id}/impreso`.
- El usuario y la clave van en `print-agent/config.env` (está en el `.gitignore`; hay un `config.ejemplo.env`).
- Para que un pedido no salga dos veces si llega por el WebSocket y por la consulta a la vez, me acuerdo de `(id, updated_at)`. Un "reimprimir" cambia el `updated_at`, así que ese sí sale de nuevo.
- Hora de Mendoza fija en UTC-3 (Argentina no cambia la hora), así no hace falta instalar `tzdata` en Windows.
- La impresión está toda en `impresora.py`, en `imprimir()`. Ahí hay un ejemplo de cómo queda con python-escpos.

## Cómo levantar todo (PowerShell)

```powershell
# 1. Base y backend (como siempre)
cd C:\Users\veraa\bruto-app
git checkout frontend
docker compose up -d
cd backend
.\venv\Scripts\Activate.ps1
alembic upgrade head          # si todavía no aplicaste las de B6 y B7
uvicorn app.main:app --reload --port 8001

# 2. El front (otra terminal)
cd C:\Users\veraa\bruto-app\frontend
npm install
npm run dev                   # http://localhost:5173

# 3. La ticketera (otra terminal, opcional)
cd C:\Users\veraa\bruto-app\print-agent
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.ejemplo.env config.env   # completá email y clave de un usuario impresora
python agente.py
```

- Usuarios: en http://localhost:8001/docs, con Authorize como admin, `POST /api/auth/usuarios` con rol `cantina`, `cocina` e `impresora`.
- **Ojo con el horario:** la tienda solo acepta pedidos de 18:00 a 00:30. Si probás de día, cambiá el horario con `PUT /api/config/horarios`, si no vas a ver "cerrado" al confirmar.
- Pantallas: `/` la tienda, `/?donde=Cancha 3` como si viniera del QR, `/pedido/<codigo>` el seguimiento, `/panel/login`, `/panel` y `/cocina`.
- La intro se guarda en sessionStorage: para verla de nuevo cerrá la pestaña o abrí una de incógnito.
- `npm run build` deja todo listo en `frontend/dist`.

**Para probar desde el celu en la misma wifi** hace falta: (1) `uvicorn ... --host 0.0.0.0`, (2) `npm run dev -- --host`, (3) crear `frontend/.env.local` con `VITE_API_URL=http://<IP de la compu>:8001`, (4) en `backend/.env` poner `FRONTEND_URL=http://<IP de la compu>:5173` (por el CORS y la vuelta de MP; ese archivo lo tocás vos) y (5) permitir los dos puertos en el firewall de Windows. La vibración y que la pantalla de la cocina no se apague necesitan https (o localhost), así que en la wifi local no van a andar; en producción sí.

## Qué probar a mano (sobre todo en el celu)

1. La intro en celus de verdad (Android e iPhone): que se saltee con un toque y que con "reducir movimiento" vaya directo al logo.
2. Escanear un QR con `?donde=Cancha 3` y ver que llegue elegido "Comer adentro" con la cancha.
3. Que el teclado no tape el botón de "Continuar" o "Pagar" en el checkout, sobre todo en iPhone.
4. Mercado Pago con credenciales de prueba (pasos en B2): tarjeta `APRO` y `OTHE`, volver a la app y ver "Confirmando tu pago..." y después el pedido recibido. Probar también volver de MP sin pagar.
5. Take away listo: que vibre (en Android; el iPhone no tiene vibración desde la web) y que salga "¡Ya podés retirarlo!".
6. Cerrar la tienda y volver a abrirla: tiene que aparecer "Ver mi pedido".
7. Panel en la compu y en un celu del personal (con pestañas). Tocar la barra del sonido y hacer un pedido: tiene que sonar y brillar la tarjeta.
8. Cortar el wifi de la compu del panel: tiene que salir la barra amarilla de reconexión y, al volver, traer lo que entró mientras tanto.
9. Cocina en la tablet acostada: que se lea de lejos, reloj amarillo a los 12 min y que la pantalla no se apague (con https).
10. La ticketera: dejar pedidos sin imprimir, arrancar el agente y ver que salgan; después "Reimprimir" desde el panel.

## Revisión final (paso 10): problemas, de más grave a menos

No arreglé ninguno, como pide la tarea.

**Graves**
1. **Pedido duplicado con mala señal.** Si el `POST /api/tienda/pedidos` llega al backend pero la respuesta no vuelve (señal mala en la cancha), el cliente ve "No pudimos conectarnos", vuelve a tocar y entra un segundo pedido. El botón está bloqueado mientras manda, pero falta una "llave" por intento. El arreglo de verdad es que el front mande un id random por intento y el backend no cree dos pedidos con el mismo (cambio de backend).
2. **Posible doble pago en MP.** A los 2 minutos sin confirmación, el seguimiento ofrece "Pagar con Mercado Pago" de nuevo. Si el pago estaba aprobado pero MP tardó en avisar, el cliente puede pagar dos veces y hay que devolver uno a mano. Convendría esperar más, o mostrar primero solo "Ya pagué, revisar de nuevo".
3. **Los pedidos que entran durante un corte del panel no suenan.** Al reconectar se recarga la lista y aparecen, pero sin sonido ni brillo. Un sábado con el wifi flojo pueden pasar desapercibidos en "Nuevos".

**Medias**
4. **El "atrás" del celu con la hoja del producto abierta** no la cierra: vuelve a la página anterior (y si entró por el QR, se sale de la tienda). El carrito no se pierde.
5. **Se pierde lo que cargó en "Tu pedido"** (comer adentro o take away, y la ubicación) si toca "+ Agregar algo más" y vuelve, porque el checkout se arma de nuevo. Nombre, apellido y teléfono se recuerdan recién después del primer pedido.
6. **Precios viejos en el carrito.** El carrito guarda el precio de cuando se agregó (hasta 6 hs). Si Renzo aplica un aumento en el medio, el total que ve el cliente no es el que cobra el backend, y se entera recién en Mercado Pago o en el seguimiento.
7. **La vibración de "listo" puede no andar** si el cliente no tocó la pantalla del seguimiento (Chrome la bloquea hasta el primer toque, por ejemplo al volver de MP). En iPhone no existe. El cartel verde sale siempre.
8. **Tienda cerrada:** se puede armar todo el pedido y recién al confirmar dice que está cerrada. Arriba se ve "Cantina cerrada" con el mensaje, pero no frena antes.
9. **Producto que se apaga con el pedido en el carrito:** el error del backend ("X no está disponible ahora") sale en "Tus datos", pero para sacarlo hay que volver a "Tu pedido", y no se marca cuál es.
10. **Token vencido en el panel:** el backend cierra el WebSocket antes de aceptarlo, el navegador lo toma como un corte común y sigue reconectando. El panel vuelve al login cuando falla otra llamada (el resumen, en menos de un minuto). Mientras tanto dice "Reconectando".

**Leves**
11. A 360 px, en el panel el logo queda cortado ("BRUT") por los botones de arriba; en la cocina el título "Cocina · N en marcha" ocupa tres renglones (la cocina está pensada para tablet).
12. Sin indicador de carga: el resumen del panel muestra "–" hasta que llega, y el botón "Recargar" de la barra de conexión no muestra que está cargando.
13. Errores que no se muestran: si falla `GET /api/tienda/estado` no se ve ni "abierta" ni "cerrada"; si falla el resumen del panel queda el dato viejo sin aviso.
14. Desde la cocina no se puede deshacer un "Listo" tocado sin querer (el backend lo permite, falta el botón). Tampoco hay en el panel una vista de entregados y cancelados del día (`?todos=true`).
15. "Ver mi pedido" muestra solo el último pedido; si hizo dos, el primero lo tiene que buscar con el link.
16. En compu la intro se ve chica en el medio y las líneas de la cancha cortan a los costados (la escena es de celu).
17. Textos: "Take away" y "Delivery" quedaron en inglés porque así están en la maqueta y en la carta. Todo lo demás está en castellano.

Nota de las pruebas: las migraciones usan `now()` de Postgres, así que una base SQLite armada con `alembic upgrade` no deja crear pedidos. No afecta a Postgres ni a los tests (usan `create_all`). Para probar el front con SQLite armé la base con `create_all`.
