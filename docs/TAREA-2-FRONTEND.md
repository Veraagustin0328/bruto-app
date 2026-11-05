# Tarea 2 · Frontend completo de BRUTO

Vas a trabajar solo, sin preguntarme nada. Yo no voy a estar mirando. Esta tarea es larga: tomate tu tiempo y hacela bien.

Antes de arrancar, leé enteros el CLAUDE.md, DECISIONES.md (lo dejó la tarea del backend), el código de backend/ y abrí docs/BRUTO-pantallas.html y docs/intro-bruto.html. Las maquetas son la referencia de diseño: copiá su estética, colores, tipografías y espaciados.

## Cómo trabajar

1. Creá una rama nueva desde la del backend y trabajá solo ahí: `git checkout backend-pendientes` y después `git checkout -b frontend`. Nunca toques main
2. Hacé los pasos 1 a 9, en orden
3. Para probar, levantá vos el backend (uvicorn en el puerto 8001, con la base SQLite de los tests o la de Docker si está corriendo) y el front (Vite en el 5173)
4. Al terminar cada paso: `npm run build` tiene que andar sin errores, y revisá en el navegador que la pantalla cargue y hable con el backend. Si tenés Playwright disponible, sacá una captura de cada pantalla a 390 px de ancho (celu) y a 1280 px, y revisala
5. Cuando el paso anda, commit con un mensaje que diga el paso, por ejemplo "Front 3: armar producto y carrito"
6. Donde un paso dice "esperá" o "decime antes", no esperes: elegí lo más simple y anotalo en DECISIONES.md, en una sección nueva "Frontend"
7. Si para que algo ande hace falta cambiar el backend, hacelo solo si es chico y con su test, y anotalo. Si es grande, anotalo y seguí
8. Si te trabás en un paso después de varios intentos, anotalo, no commitees ese paso y seguí con el siguiente si no depende de ese
9. Prohibido: tocar el .env, hacer git push, hacer el deploy, librerías de componentes pesadas (nada de Material UI ni parecidos: Tailwind y listo)
10. Todos los textos de la app en español argentino, cortos y claros. Comentarios del código también

## Al terminar

Escribí al final de DECISIONES.md, en la sección Frontend:
- Qué pantallas quedaron hechas y cuáles no
- Las decisiones que tomaste vos
- Cómo levanto todo en mi compu con PowerShell, paso a paso
- Qué tengo que probar a mano, sobre todo en el celu
- Al final, hacé la revisión del paso 10 y dejá la lista de problemas ordenada por gravedad, sin arreglarlos

---

## Los pasos

### 1. Crear el frontend

Creá el frontend en la carpeta frontend con React + Vite + Tailwind, en JavaScript (no TypeScript). Corré vos los comandos.

Quiero:
- React Router con estas rutas: / (tienda), /pedido/:codigo (seguimiento), /panel/login, /panel (cantina), /cocina
- Tailwind configurado con los colores y fuentes de la marca que están en el CLAUDE.md (Bebas Neue y Poppins de Google Fonts)
- Un archivo src/api.js con la URL del backend en una variable de entorno VITE_API_URL (http://localhost:8001 en desarrollo) y funciones para llamar a cada ruta
- Mové llama.png y bruto-blanco.png a src/assets
- Cada ruta por ahora muestra solo su nombre, para ver que el router anda

Al final decime cómo levantarlo y qué tengo que ver en el navegador.

### 2. Tienda: la carta

Armá la pantalla de la tienda (/) igual a la pantalla "1 · La carta" de docs/BRUTO-pantallas.html.

- Trae el menú de GET /api/tienda/menu
- Arriba el logo y "Cantina abierta"
- Chips de categorías que al tocarlos hacen scroll a esa categoría
- Cada producto con foto, nombre, descripción en 2 líneas, precio y el doble si tiene grupo Tamaño
- La etiqueta (ej: "Recomendada") como badge naranja
- Los que tienen disponible: false se ven apagados y no se pueden tocar
- Mientras carga, un esqueleto. Si falla, un mensaje con botón para reintentar
- Pensado para celu (360 a 430 px de ancho). En compu, centrado con ancho máximo

Las fotos por ahora no están en el backend (imagen_url viene null): mostrá un placeholder oscuro con la llama.

### 3. Tienda: armar el producto y el carrito

Sumá a la tienda:

1. Al tocar un producto se abre una hoja de abajo (bottom sheet) como la pantalla "2 · Armar la burger" de docs/BRUTO-pantallas.html:
   - Grupos de opciones según lo que viene del menú: los de tipo "unica" con radio, los "multiple" con stepper si cantidad_max es null o mayor a 1
   - Respetá obligatorio, max_selecciones, cantidad_max y las opciones no disponibles ("Hoy no hay")
   - Campo de nota ("Sin pepinillos")
   - Botón "Agregar · $precio" que se actualiza en vivo. No deja agregar si falta un obligatorio
2. Un carrito guardado en un contexto de React y en localStorage (con try/catch), así no se pierde si recarga
3. La barra naranja de abajo "Ver mi pedido · cantidad · total" cuando hay algo en el carrito

El precio que muestra el front es solo para mostrar: el que vale es el que devuelve el backend al crear el pedido.

### 4. Tienda: dónde comés, datos y pago

Armá el checkout siguiendo las pantallas 3 y 4 de docs/BRUTO-pantallas.html:

1. Lista del pedido con opciones y notas, y poder cambiar cantidades o sacar items
2. "¿Dónde lo comés?" con tres opciones: Comer adentro, Take away y Delivery
   - Comer adentro: input de ubicación con placeholder "Ej: frente a la cancha 3", obligatorio, y botones rápidos Cancha 1 a 4 que lo completan. Si la URL trae ?donde=Cancha 3 (por el QR de la cancha), que ya venga elegido y completo
   - Take away: sin ubicación
   - Delivery: no arma pedido. Muestra un botón que abre el link de PedidosYa. Dejá el link en una constante en src/config.js con un TODO, que todavía no lo tenemos
3. Nombre, apellido y teléfono, los tres obligatorios
4. Mercado Pago o efectivo
5. Al confirmar: POST /api/tienda/pedidos. Si es efectivo, va directo a /pedido/:codigo. Si es MP, pide POST /api/pagos/{codigo}/preferencia y redirige a link_pago
6. Los errores que devuelve el backend (detail) se muestran tal cual arriba del botón. Ya vienen escritos para el cliente
7. Guardá nombre, apellido y teléfono en localStorage para la próxima vez

### 5. Seguimiento del pedido

Armá /pedido/:codigo como la pantalla "5 · Seguimiento" de docs/BRUTO-pantallas.html:

- Trae el pedido con GET /api/tienda/pedidos/{codigo}
- Si viene de Mercado Pago (el pedido está en pendiente_pago), llamá a POST /api/pagos/{codigo}/verificar al entrar y cada 5 segundos hasta que cambie, máximo 2 minutos. Mientras, mostrá "Confirmando tu pago..."
- Si el pago fue rechazado, botón para volver a pagar (pide una preferencia nueva)
- Conectate a WS /ws/pedido/{codigo} para actualizar en vivo. Mandá "ping" cada 25 s y reconectá solo si se corta
- Número grande, línea de tiempo con los estados, a dónde se lo llevan y si está pagado
- Cuando pasa a "listo" en take away: un aviso bien visible de "Ya podés retirarlo" y que vibre el celu si se puede
- Guardá el código del último pedido en localStorage, así si cierra y abre la tienda le aparece un acceso a "Ver mi pedido"

### 6. La intro del paletazo

Pasá la animación de docs/intro-bruto.html a un componente React (IntroBruto) que se muestre al entrar a la tienda:

- Misma secuencia y tiempos: pelota, paletazo, llama, BRUTO, Food & Grill
- Se muestra una sola vez por visita (sessionStorage con try/catch)
- Con un toque en cualquier parte se saltea
- Si el celu tiene prefers-reduced-motion, va directo al logo
- Al terminar, desaparece con un fade y queda la carta
- Sin librerías de animación, con CSS como en la maqueta

### 7. Login y panel de la cantina

Armá el panel de la cantina siguiendo la parte 2 de docs/BRUTO-pantallas.html:

1. /panel/login: email y contraseña contra POST /api/auth/login (va como formulario, username y password). Guardá el token y el usuario
2. /panel protegido: si no hay token o el backend devuelve 401, vuelve al login
3. Arriba los 4 cuadros de GET /api/panel/resumen
4. Tres columnas: Nuevos (recibido), En preparación, Listos para llevar. En celu, las columnas pasan a pestañas
5. Cada tarjeta: número, hace cuánto entró, modo, ubicación en grande, nombre y teléfono, items con opciones y notas en naranja, y si está pagado o hay que cobrar
6. Botones según el estado: "A la cocina", "Listo", "Entregado", "Cobrar" (si es efectivo y no está cobrado), "Reimprimir" y "Cancelar" con confirmación hecha en la página (nada de confirm())
7. Conectate a WS /ws/panel?token=... y actualizá las tarjetas en vivo. Cuando entra un pedido_nuevo, que suene un aviso y la tarjeta brille unos segundos. El sonido arranca recién después de que el usuario toca algo, por las reglas del navegador
8. Si se corta el WebSocket, mostralo arriba y reconectá solo

### 8. Pantalla de cocina

Armá /cocina como la parte 3 de docs/BRUTO-pantallas.html, pensada para una tablet acostada:

- Mismo login que el panel (rol cocina, cantina o admin)
- Solo pedidos recibido y en_preparacion, en tarjetas grandes con letra para leer de lejos
- Reloj en cada comanda desde que entró. Se pone amarillo a los 12 minutos
- Botón grande: "Empezar" si está recibido, "Listo" si está en preparación
- Las notas en amarillo y mayúsculas
- En vivo por WebSocket, con sonido al entrar uno nuevo
- Que la pantalla no se apague (Wake Lock API, si el navegador la soporta)

### 9. Agente de la ticketera (simulado)

Creá la carpeta print-agent con un script Python aparte del backend:

- Se loguea con un usuario de la cantina y se conecta a /ws/panel
- Cuando llega un pedido en estado recibido con impreso_at vacío, arma la comanda como la de docs/BRUTO-pantallas.html (número, modo, ubicación en grande, nombre, items con opciones, notas resaltadas, pagado o "COBRAR $...")
- Por ahora la "imprime" en la consola y en un archivo de texto, con 48 caracteres de ancho (papel de 80 mm)
- Dejá la impresión detrás de una función, así cuando tengamos el modelo de la impresora solo cambiamos eso por python-escpos

Usá las rutas de impresión que armó la tarea del backend (paso B6, fijate en DECISIONES.md cómo quedaron) para traer los pendientes y marcarlos como impresos. Al arrancar, tiene que imprimir lo que haya quedado pendiente (por si se cortó internet).

### 10. Revisión final

Revisá todo el frontend como si fueras un cliente con el celu en la cancha y como si fueras el de la cantina un sábado a la noche lleno de pedidos. Buscá:
- Pantallas que se rompen en celus chicos (360 px)
- Textos en inglés o que suenan raros
- Cosas que tardan sin mostrar que están cargando
- Errores que no se le muestran al usuario
- Botones que se pueden tocar dos veces y duplican pedidos

Dejá la lista en DECISIONES.md, ordenada por gravedad, y no arregles nada.
