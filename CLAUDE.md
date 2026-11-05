# BRUTO · sistema de pedidos

App de pedidos para **BRUTO Food & Grill**, la cantina de un complejo de canchas de pádel en Mendoza. El cliente escanea un QR, pide desde el celu y elige:

- **Comer adentro**: escribe dónde está ("frente a la cancha 3") y los chicos de la cantina se lo llevan
- **Take away**: alguien de afuera pide y retira en la cantina
- **Delivery**: NO lo hacemos nosotros. Es un botón que abre la tienda de BRUTO en PedidosYa (o la app que confirme el cliente). Esos pedidos no entran a nuestro sistema

Pago con Mercado Pago (Checkout Pro) o efectivo. Es para un solo local.

## Stack

- **Backend** (`backend/`): FastAPI + SQLAlchemy 2 + PostgreSQL 16 + Alembic. Ya está hecho y probado
- **Frontend** (`frontend/`): React + Vite + Tailwind. Mobile first: la tienda se usa casi siempre desde el celu
- **Agente de impresión** (`print-agent/`, a futuro): script Python que corre en la PC de la cantina e imprime las comandas con `python-escpos`

## Cómo levantar todo (Windows, PowerShell)

```powershell
cd C:\Users\veraa\bruto-app
docker compose up -d                      # Postgres en el puerto 5433
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8001 # API en http://localhost:8001/docs
```

Puertos: el **5432 y el 8000 los usa otro proyecto** (ecommerce) en esta compu. BRUTO usa **5433** (Postgres) y **8001** (API). El front va en el **5173** (Vite).

Scripts útiles (en `backend`, con el venv activado):
- `python -m scripts.seed` carga la carta de BRUTO y crea el admin (no duplica si ya está)
- `python -m scripts.escuchar_panel` muestra en la terminal los pedidos en tiempo real

## Reglas para trabajar en este repo

- Hablame en español argentino, informal. Los comentarios del código también, cortos y que no suenen a robot
- Trabajamos **paso a paso**: hacé una parte, mostrame cómo probarla y esperá que te confirme antes de seguir
- Cuando cambies un archivo, mostrame **el archivo completo**, no diffs sueltos
- Los comandos que me pases son para **PowerShell**, no bash (nada de `touch`, `mkdir -p` ni `{a,b}`)
- Nunca subas el `.env` ni pegues tokens o contraseñas en el código
- El precio SIEMPRE lo calcula el backend. El front muestra precios pero nunca los manda como verdad
- Antes de cambiar algo del backend que ya funciona, avisame y explicame por qué

## Backend: lo que ya existe

Modelos en `backend/app/models/`: `Categoria`, `Producto`, `GrupoOpciones` (tipo `unica` o `multiple`, `obligatorio`, `max_selecciones`), `Opcion` (`precio_extra`, `cantidad_max` donde None = ilimitado), `Pedido`, `PedidoItem`, `PedidoItemOpcion`, `Usuario` (roles `admin`, `cantina`, `cocina`).

Estados de un pedido: `pendiente_pago` (MP sin confirmar, la cocina no lo ve) → `recibido` → `en_preparacion` → `listo` → `entregado`. También `cancelado`. La numeración (#001, #002...) se reinicia todos los días a las 6 AM, porque la cantina cierra pasada la medianoche.

### Rutas públicas (el celu del cliente, sin login)
- `GET /api/tienda/menu` → categorías con productos, grupos y opciones. Los productos con `disponible: false` se muestran apagados (ej: Pepperoni "Próximamente")
- `POST /api/tienda/pedidos` → crea el pedido. Body: `modo`, `ubicacion` (obligatoria si es comer adentro), `nombre`, `apellido`, `telefono`, `metodo_pago`, `notas`, `items[]` con `producto_id`, `cantidad`, `nota` y `opciones[]` (`opcion_id`, `cantidad`). Devuelve el pedido con su `codigo` (largo y random) y su `numero`
- `GET /api/tienda/pedidos/{codigo}` → estado del pedido para la pantalla de seguimiento
- `POST /api/pagos/{codigo}/preferencia` → devuelve `link_pago` de Mercado Pago
- `POST /api/pagos/{codigo}/verificar` → le pregunta a MP si se pagó. El celu lo llama al volver de MP
- `WS /ws/pedido/{codigo}` → el celu recibe `{evento, pedido}` cada vez que cambia su pedido. Mandar `"ping"` cada 25 s (responde `"pong"`)

### Rutas del panel (con login)
- `POST /api/auth/login` → formulario `username` (email) + `password`. Devuelve `access_token` y `usuario`
- `GET /api/auth/yo` → usuario logueado
- `GET/POST/PATCH /api/auth/usuarios` → solo admin
- `GET /api/panel/pedidos` → activos de la jornada (`?todos=true` trae también entregados y cancelados)
- `GET /api/panel/resumen` → `pedidos`, `vendido`, `efectivo_a_cobrar`, `esperando_pago_mp`
- `PATCH /api/panel/pedidos/{id}/estado` → `{"estado": "..."}`. La cocina solo puede pasar a `en_preparacion` y `listo`
- `POST /api/panel/pedidos/{id}/cobrar` → marca cobrado un pedido en efectivo
- `POST /api/panel/pedidos/{id}/reimprimir` → vacía `impreso_at` para que la ticketera lo saque de nuevo
- `WS /ws/panel?token=...` → recibe `pedido_nuevo` y `pedido_actualizado` con el pedido completo

Todas las rutas del panel van con `Authorization: Bearer <token>`. El token dura 12 hs.

## Diseño

Las maquetas de referencia están en `docs/`:
- `docs/BRUTO-pantallas.html`: todas las pantallas (tienda en el celu, panel de la cantina, cocina, comanda impresa, precios). Abrilo en el navegador antes de armar cualquier pantalla
- `docs/intro-bruto.html`: la animación de bienvenida (la pala le pega a la pelota y sale la llama con BRUTO)

Marca (del manual de marca):
- Colores: naranja `#F05C2B`, negro y blanco. Todo en fondo oscuro
- Tipografías de la marca: Bradley (títulos) y Made Tommy (textos). Mientras no tengamos los archivos, usar **Bebas Neue** para títulos y **Poppins** para textos, de Google Fonts
- Logo: la llama (isotipo) y la palabra BRUTO (logotipo) se pueden usar por separado. Están en `frontend/src/assets/` (`llama.png`, `bruto-blanco.png`)

## Pendiente con el cliente

- Datos de la ticketera (marca, conexión, ancho de papel)
- Cantidad de canchas, para los QR (un QR por cancha que ya complete la ubicación con `?donde=Cancha 3`)
- Horario de la cantina, precio de la opción veggie y link de la tienda en PedidosYa
- Cuenta de Mercado Pago de producción
