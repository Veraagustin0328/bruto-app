# Tarea 3 · Arreglos, pantallas de admin y caja del día

Vas a trabajar solo, sin preguntarme nada. Yo no voy a estar mirando. Esta tarea es larga: tomate tu tiempo y hacela bien.

Antes de arrancar, leé enteros el CLAUDE.md, DECISIONES.md (las secciones del backend y del frontend, sobre todo la revisión del final) y el código de backend/ y frontend/. Para el diseño, seguí usando docs/BRUTO-pantallas.html: la parte 4 muestra la pantalla de precios.

## Cómo trabajar

1. Creá una rama nueva desde frontend y trabajá solo ahí: `git checkout frontend` y después `git checkout -b admin`. Nunca toques main
2. Hacé las partes A, B y C, en orden
3. Al terminar cada paso: corré TODOS los tests del backend (`python -m pytest -q` en backend) y `npm run build` en frontend. Si algo falla, arreglalo antes de seguir
4. Probá cada pantalla en el navegador contra el backend real, como en la tarea 2, con capturas a 390 px y a 1280 px. Usá una base SQLite aparte, no mi Postgres de Docker
5. Cuando un paso anda, commit con un mensaje que diga el paso, por ejemplo "A1: no duplica pedidos con mala señal"
6. Cada cambio en el backend lleva sus tests. Si cambia el modelo de datos, migración con Alembic probada contra una SQLite vacía
7. Donde haya que decidir algo, elegí lo más simple y seguro, y anotalo en DECISIONES.md en una sección nueva "Tarea 3"
8. Si te trabás en un paso después de varios intentos, anotalo, no commitees ese paso y seguí con el siguiente si no depende de ese
9. Prohibido: tocar el .env, hacer git push, hacer el deploy, borrar datos de mi base de Docker, librerías de componentes pesadas
10. Todo en español argentino: textos de la app y comentarios del código

## Al terminar

Escribí al final de DECISIONES.md, en la sección "Tarea 3":
- Qué quedó hecho y qué no
- Cuántos tests hay y si pasan todos
- Las decisiones que tomaste vos
- Los comandos de PowerShell para aplicar las migraciones nuevas en mi base de Docker
- Qué tengo que probar a mano
- La lista de la revisión del frontend actualizada: cuáles quedaron arreglados y cuáles no

---

## Parte A · Arreglos de la revisión

### A1. Pedido duplicado con mala señal

- El front genera un código único (crypto.randomUUID) por cada intento de checkout, lo guarda en sessionStorage y lo manda en el header Idempotency-Key en POST /api/tienda/pedidos. Si el pedido se crea bien, se borra. Si falla y el cliente reintenta, se manda el mismo código
- El backend guarda ese código en el pedido (columna nueva, única, con su migración). Si llega uno repetido, devuelve el pedido que ya existe en vez de crear otro, y no lo cuenta para los límites de B4
- Tests: dos POST con el mismo código crean un solo pedido y devuelven el mismo número

### A2. Pagar dos veces en Mercado Pago

- Antes de ofrecer "Pagar de nuevo", el front llama a /verificar. Solo muestra el botón si MP dice que el pago fue rechazado o que no hay ningún pago. Si está pendiente o en proceso, muestra "Mercado Pago todavía está procesando tu pago" y sigue esperando
- El backend, en POST /preferencia, le pregunta a MP si ya hay un pago aprobado o en proceso para ese pedido. Si lo hay, no crea otro link: devuelve 400 con un mensaje claro
- Tests con el SDK simulado

### A3. Pedidos que entran durante un corte del panel

- Cuando el WebSocket del panel y el de la cocina se reconectan, traen la lista de nuevo y la comparan con la que tenían. Los pedidos recibidos que no estaban suenan y brillan como si hubieran entrado recién
- Mientras está cortado, un cartel bien visible arriba: "Sin conexión, reconectando..."

### A4. El resto de la revisión

Seguí con el resto de la lista de la revisión del frontend que está en DECISIONES.md, de los más graves a los menos, salvo los que necesiten datos de Renzo.

---

## Parte B · Pantallas para Renzo (admin)

Hoy el backend tiene todo para manejar la carta, los precios, el horario y los usuarios, pero solo se puede usar desde /docs. Renzo necesita pantallas. Todas dentro del panel, con el mismo login, y pensadas para usarse también desde el celu.

### B1. Menú del panel según el rol

- Arriba del panel, pestañas según quién entra:
  - admin: Pedidos, Cocina, Carta y precios, Caja, Configuración, Usuarios
  - cantina: Pedidos, Cocina, Caja (solo la del día) y el interruptor de pausar pedidos
  - cocina: solo Cocina
- Si alguien entra a una pantalla que no le corresponde, lo manda a la suya

### B2. Carta y precios

Como la parte 4 de docs/BRUTO-pantallas.html:

- Lista de la carta por categoría, con cada producto, su precio y un interruptor de disponible. La cantina también puede usar el interruptor (para la bondiola sin stock)
- Tocar el precio lo deja editar ahí mismo y se guarda al confirmar
- Aumento de precios: elegir a qué aplica (todo, una categoría o productos sueltos), el porcentaje y el redondeo. Muestra la vista previa con precio viejo tachado y precio nuevo, y recién ahí un botón "Aplicar a N precios"
- Crear, editar y borrar productos, con sus grupos de opciones y opciones (nombre, precio extra, cantidad máxima, disponible). Borrar pide confirmación en la página
- Subir la foto de cada producto (la ruta del backend ya existe). Que se vea cómo queda antes de guardar
- Reordenar categorías y productos con flechitas de subir y bajar (nada de arrastrar, que en el celu es incómodo)
- Si otro usuario cambia la carta, se actualiza sola (evento carta_actualizada)

### B3. Configuración

- Horario de cada día de la semana, con apertura y cierre. Tiene que entender que 18:00 a 00:30 cruza la medianoche
- Interruptor grande de "Pausar pedidos", con el mensaje que ve el cliente. También va en la pantalla de Pedidos para la cantina. Si el backend solo deja pausar al admin, cambialo para que también pueda la cantina, con su test
- Link de la tienda de PedidosYa
- La tienda tiene que mostrar en vivo si está abierta, cerrada o pausada

### B4. Usuarios

- Lista de usuarios con su rol y si están activos
- Crear usuario: nombre, email, contraseña y rol
- Cambiar rol, dar de baja y volver a dar de alta
- Cambiarle la contraseña a alguien que se la olvidó
- Que Renzo no se pueda sacar el admin ni dar de baja a sí mismo (el backend ya lo frena, mostrá bien el error)

---

## Parte C · Caja del día

### C1. Backend

Una ruta nueva GET /api/panel/caja?fecha=AAAA-MM-DD (sin fecha, la jornada de hoy, que arranca a las 6 AM):
- Total vendido, separado en Mercado Pago y efectivo cobrado
- Efectivo pendiente de cobrar
- Cantidad de pedidos, ticket promedio y cuántos se cancelaron
- Pedidos por modo: comer adentro y take away
- Los 10 productos más vendidos, con cantidad y plata
- Ventas por hora, para ver a qué hora se llena
- La cantina solo puede ver la jornada de hoy. El admin, cualquier fecha
- Y GET /api/panel/caja/historial?desde=&hasta= (solo admin): total por día, para los últimos 30 días por defecto
- Tests de todo, con pedidos de ejemplo en distintos estados, horarios y métodos de pago

### C2. Frontend

- Pantalla "Caja" con los números de arriba en cuadros, los productos más vendidos y un gráfico simple de ventas por hora (hecho con SVG o CSS, sin librerías de gráficos)
- El admin puede elegir la fecha y ver el historial de los últimos 30 días
- Botón "Copiar resumen" que copia un texto corto para mandar por WhatsApp, tipo: "BRUTO · Jueves 5/11 · 37 pedidos · $612.500 (MP $480.000 / efectivo $132.500)"
