# Tarea 1 · Backend completo de BRUTO

Vas a trabajar solo, sin preguntarme nada. Yo no voy a estar mirando. Esta tarea es larga: tomate tu tiempo y hacela bien.

Antes de arrancar, leé enteros el CLAUDE.md, todo el código de backend/ y docs/BRUTO-pantallas.html.

## Cómo trabajar

1. Creá una rama nueva y trabajá solo ahí: `git checkout -b backend-pendientes`. Nunca toques main
2. Antes de cambiar nada, escribí tests con pytest de lo que YA funciona: menú, crear pedido (precio con doble y extras, validaciones), numeración del día, login y permisos por rol, panel (transiciones, cobrar, reimprimir, resumen) y WebSockets. Usá SQLite en memoria, sin tocar el Postgres de Docker. Que pasen todos y hacé un commit
3. Después hacé los pasos B1 a B8, en orden. Cada cosa nueva lleva sus tests
4. Al terminar cada paso: corré TODOS los tests. Si alguno falla, arreglalo antes de seguir. Cuando pasen, commit con un mensaje que diga el paso, por ejemplo "B3: cancela pedidos de MP sin pagar"
5. Donde un paso dice "esperá que te diga que sí", "decime antes" o "mostrame primero", no esperes: elegí la opción más simple y segura, y anotala en DECISIONES.md (en la raíz del repo) con el motivo
6. Si algo necesita datos que no tenés (credenciales de Mercado Pago, datos de Renzo), hacelo igual, probalo con el SDK simulado o con valores de ejemplo, y anotá en DECISIONES.md qué quedó pendiente
7. Si cambia el modelo de datos, generá la migración con Alembic y probala contra una base SQLite vacía
8. Si en un paso te trabás de verdad después de varios intentos: anotalo en DECISIONES.md, no commitees ese paso, y seguí con el siguiente si no depende de ese
9. Prohibido: tocar el .env, hacer git push, hacer el deploy, borrar datos de la base de Docker, cambiar la lógica de precios sin un test que lo cubra
10. Comentarios del código en español argentino, cortos

## Al terminar

Escribí al final de DECISIONES.md:
- Qué pasos quedaron hechos y cuáles no
- Cuántos tests hay y si pasan todos (con el comando para correrlos)
- Las decisiones que tomaste vos
- Lo que tengo que probar a mano y lo que hay que pedirle a Renzo
- Los comandos de PowerShell para aplicar las migraciones nuevas en mi base de Docker

---

## Los pasos

Antes del B2 fijate que estén los archivos de docs/mercadopago/. Si no están, escribí Mercado Pago vos siguiendo lo que pide el paso y anotalo.

### B1. Arreglos de la revisión

Arreglá estos problemas que encontraste en la revisión. Anotá en DECISIONES.md, en una línea por punto, qué cambiaste.

1. Los pedidos en pendiente_pago no tienen que llegarle al panel ni a la cocina:
   - En avisar_pedido (app/ws.py), si el pedido está en pendiente_pago no le mandes nada a la sala "panel". Al celu del cliente sí
   - Cuando un pedido pasa de pendiente_pago a recibido (lo va a hacer Mercado Pago), a la sala "panel" mandale el evento "pedido_nuevo" y no "pedido_actualizado", así suena el aviso en la cantina
   - En GET /api/panel/pedidos con ?todos=true, la cocina no tiene que ver los pendiente_pago. La cantina y el admin sí
2. Dejá un solo requirements.txt, el de backend/, que es el completo. Si hay otro en la raíz, borralo
3. En app/config.py, que el .env se busque siempre en la carpeta backend, sin importar desde dónde se corra (usá la ruta del archivo con pathlib)
4. Pedido en efectivo sin cobrar: no se puede pasar a "entregado". Devolvé 400 con "Cobralo antes de marcarlo entregado". Sumá una ruta POST /api/panel/pedidos/{id}/cobrar-y-entregar que haga las dos cosas juntas, que es lo que va a usar el chico de la cantina
5. Pedido de Mercado Pago ya pagado: solo el admin lo puede cancelar, y la respuesta tiene que avisar "Acordate de devolver el pago desde Mercado Pago"

No toques nada más. Al final decime cómo probar cada punto en /docs.

### B2. Mercado Pago

En docs/mercadopago/ te dejé dos archivos de Mercado Pago que ya están probados: services_pagos.py va en app/services/pagos.py y routers_pagos.py va en app/routers/pagos.py.

1. Leelos enteros antes de copiarlos y decime si ves algo que choque con lo que arreglamos en el paso anterior
2. Copialos a su lugar y sumá el router en app/main.py
3. Cuando un pago se aprueba, el aviso al panel tiene que ser "pedido_nuevo" (por lo del paso anterior)
4. Fijate que mercadopago esté en requirements.txt

Después explicame cómo probarlo con las credenciales de prueba de MP: qué pongo en el .env, qué tarjeta de prueba uso y en qué orden llamo a las rutas en /docs. No me pidas que te pase el token.

### B3. Pedidos de MP que nadie pagó

Si alguien elige Mercado Pago y no paga, el pedido queda en pendiente_pago para siempre.

Hacé que se cancelen solos los que lleven más de 30 minutos en pendiente_pago:
- Una tarea que corra cada minuto dentro de FastAPI (con lifespan y asyncio, sin librerías nuevas)
- Antes de cancelar uno, preguntale a Mercado Pago con verificar_pedido por si se pagó y no nos llegó el aviso. Si se pagó, que pase a recibido en vez de cancelarse
- Si no hay MP_ACCESS_TOKEN configurado, que la tarea no haga nada y no tire errores
- Que el tiempo (30 minutos) esté en config.py

Explicame cómo probarlo sin esperar 30 minutos.

### B4. Protección contra abusos

La tienda es pública: cualquiera puede mandar pedidos falsos y llenarle la cocina a BRUTO.

Sumá límites, sin Redis (todo en memoria, alcanza con un solo proceso):
1. POST /api/tienda/pedidos: máximo 5 pedidos cada 10 minutos por IP, y máximo 3 pedidos activos (recibido, en_preparacion o listo) por teléfono a la vez
2. POST /api/auth/login: después de 5 intentos fallidos con el mismo email, bloquear ese email 15 minutos
3. Los mensajes de error, en castellano y para el cliente: "Hiciste muchos pedidos seguidos, esperá unos minutos" y parecidos
4. Que funcione detrás de un proxy (Railway), tomando la IP de X-Forwarded-For
5. Los números (5, 10, 3, 15) en config.py

### B5. Carta y precios para Renzo

Hoy la carta solo se carga con el seed. Armá las rutas para que el admin (Renzo) la maneje desde el panel. Mirá la parte 4 de docs/BRUTO-pantallas.html.

Todo en un router nuevo /api/carta, solo admin, salvo lo de disponibilidad que también lo puede hacer el rol cantina:

1. Ver toda la carta, incluidos los productos no visibles y las opciones apagadas
2. ABM de categorías, productos, grupos de opciones y opciones
3. Reordenar categorías y productos (mandando la lista de ids en el orden nuevo)
4. Prender y apagar disponible de un producto o una opción con una sola llamada (para la bondiola sin stock). Esto también lo puede hacer la cantina
5. Aumento masivo de precios:
   - Body: a qué aplica (todo, una categoría o una lista de productos), porcentaje y redondeo (100, 500 o 1000)
   - Una ruta de vista previa que devuelva precio viejo y nuevo de cada producto y de cada opción con precio extra, SIN guardar nada
   - Otra que lo aplique
   - Cuidado con el doble: el precio de "Doble" es un extra sobre el simple. Redondeá el precio final que ve el cliente (simple + extra) y recalculá el extra a partir de eso
6. Cuando cambia algo de la carta, mandá un evento "carta_actualizada" a los WebSockets del panel, así la cantina ve el cambio
7. Los pedidos ya hechos no se tocan: tienen el precio copiado

Mostrame los schemas primero y esperá que te diga que sí antes de escribir las rutas.

### B6. Rutas para la ticketera

Sumá lo que necesita el agente de impresión (print-agent, que todavía no existe):

1. GET /api/impresion/pendientes: pedidos de la jornada en recibido o en_preparacion con impreso_at vacío
2. POST /api/impresion/pedidos/{id}/impreso: marca impreso_at (ya existe marcar_impreso en services/panel.py)
3. Las dos con un rol nuevo "impresora", o con cantina y admin. Decime qué te parece mejor y por qué antes de hacerlo. Si hace falta un rol nuevo, hacé la migración
4. Cuando alguien toca "reimprimir" en el panel, que al agente le llegue por WebSocket

### B7. Horario y configuración

Hacé una tabla de configuración que Renzo pueda editar desde el panel (solo admin), con:
- Horario de la cantina por día de la semana, que puede pasar la medianoche (ej: abre 18:00, cierra 00:30)
- Link de la tienda en PedidosYa (vacío por ahora)
- Un interruptor "pausar pedidos" para cuando la cocina está desbordada
- Mensaje que se muestra cuando está cerrado o pausado

Y:
- GET /api/tienda/estado público: si está abierto, el mensaje y el link de delivery. El front lo usa para mostrar "Cantina abierta" o "Cerrado"
- POST /api/tienda/pedidos rechaza con 400 si está cerrado o pausado
- Usá la zona horaria de config.py
- Una migración con valores iniciales: todos los días de 18:00 a 00:30 (lo cambia Renzo después)

### B8. Fotos de los productos

Los productos tienen imagen_url pero está vacío.

1. Una ruta (admin) para subir la foto de un producto: que acepte jpg, png y webp de hasta 5 MB, la achique a 800 px, la convierta a webp y la guarde
2. Que en desarrollo se guarde en una carpeta backend/uploads servida por FastAPI, y que esté preparado para pasar a un storage externo en producción (dejalo detrás de una función)
3. Sumá uploads/ al .gitignore
4. Decime qué librería vas a usar para achicar las fotos antes de instalarla

### B9. Tests

No es un paso aparte: ya los fuiste escribiendo en cada paso. Al final asegurate de que estén todos los casos de esta lista y que pasen: crear pedido (precio con doble y extras, validaciones de opciones, ubicación obligatoria), numeración del día, login y permisos por rol, transiciones de estado, cobrar, los límites de B4, Mercado Pago con el SDK simulado (aprobado, rechazado, monto que no cierra, aviso repetido), carta y aumento de precios, horario, y los WebSockets.
