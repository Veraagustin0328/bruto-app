// Todo lo que habla con el backend pasa por acá

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8001").replace(/\/$/, "");

// http://... → ws://...  y  https://... → wss://...
export const WS_URL = API_URL.replace(/^http/, "ws");

const CLAVE_SESION = "bruto.sesion";

export class ApiError extends Error {
  constructor(mensaje, status = 0) {
    super(mensaje);
    this.status = status;
  }
}

// ---------- sesión del panel (token + usuario) ----------

export function leerSesion() {
  try {
    const sesion = JSON.parse(localStorage.getItem(CLAVE_SESION));
    return sesion?.token ? sesion : null;
  } catch {
    return null;
  }
}

export function guardarSesion(token, usuario) {
  try {
    localStorage.setItem(CLAVE_SESION, JSON.stringify({ token, usuario }));
  } catch {
    // Navegador en modo privado sin storage: la sesión dura lo que dure la pestaña
  }
}

export function borrarSesion() {
  try {
    localStorage.removeItem(CLAVE_SESION);
  } catch {
    // nada
  }
}

// Cuando el backend dice 401 en el panel, avisamos para volver al login
export const EVENTO_SIN_SESION = "bruto:sin-sesion";

// ---------- errores en castellano ----------

const CAMPOS = {
  nombre: "el nombre",
  apellido: "el apellido",
  telefono: "el teléfono",
  ubicacion: "dónde estás",
  notas: "las notas",
  nota: "la nota",
  items: "el pedido",
  username: "el email",
  password: "la contraseña",
  email: "el email",
  precio: "el precio",
  precio_extra: "el precio extra",
  cantidad_max: "la cantidad máxima",
  max_selecciones: "el tope de opciones",
  descripcion: "la descripción",
  etiqueta: "la etiqueta",
  porcentaje: "el porcentaje",
  link_pedidosya: "el link de PedidosYa",
  mensaje_cerrado: "el mensaje de cerrado",
  mensaje_pausado: "el mensaje de pausa",
  mensaje: "el mensaje",
  abre: "la hora de apertura",
  cierra: "la hora de cierre",
  dias: "el horario",
  fecha: "la fecha",
  desde: "la fecha de inicio",
  hasta: "la fecha de fin",
};

// FastAPI devuelve los errores de validación (422) como lista y en inglés.
// Los pasamos a algo que entienda el cliente
function mensajeDe422(detalle) {
  const primero = detalle[0];
  if (!primero) return "Revisá los datos y probá de nuevo";
  const msg = String(primero.msg || "");
  // Los que escribimos nosotros vienen como "Value error, <mensaje>"
  if (msg.startsWith("Value error, ")) {
    const texto = msg.slice("Value error, ".length);
    const campo = CAMPOS[primero.loc?.at(-1)];
    // "el teléfono no parece válido" ya se entiende solo; los del modelo entero también
    return campo && !texto.toLowerCase().includes(campo.split(" ").at(-1))
      ? `Revisá ${campo}: ${texto}`
      : texto.charAt(0).toUpperCase() + texto.slice(1);
  }
  const campo = CAMPOS[primero.loc?.at(-1)] || "los datos";
  return `Revisá ${campo}`;
}

function mensajeDeError(status, cuerpo) {
  const detalle = cuerpo?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle)) return mensajeDe422(detalle);
  if (status === 429) return "Demasiados intentos seguidos, esperá unos minutos";
  if (status >= 500) return "Se nos trabó algo del lado nuestro. Probá de nuevo en un ratito";
  return "Algo salió mal. Probá de nuevo";
}

// ---------- el fetch de siempre ----------

async function pedir(ruta, { metodo = "GET", body, form, archivo, conToken = false, extra = {} } = {}) {
  const headers = { ...extra };
  let cuerpo;

  if (form) {
    cuerpo = new URLSearchParams(form);
  } else if (archivo) {
    // multipart: el navegador pone solo el Content-Type con el boundary
    cuerpo = archivo;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    cuerpo = JSON.stringify(body);
  }

  if (conToken) {
    const sesion = leerSesion();
    if (sesion) headers.Authorization = `Bearer ${sesion.token}`;
  }

  let respuesta;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, { method: metodo, headers, body: cuerpo });
  } catch {
    throw new ApiError("No pudimos conectarnos. Revisá tu conexión y probá de nuevo", 0);
  }

  let datos = null;
  try {
    datos = await respuesta.json();
  } catch {
    // respuesta sin cuerpo
  }

  if (!respuesta.ok) {
    if (respuesta.status === 401 && conToken) {
      borrarSesion();
      window.dispatchEvent(new Event(EVENTO_SIN_SESION));
    }
    throw new ApiError(mensajeDeError(respuesta.status, datos), respuesta.status);
  }
  return datos;
}

// ---------- tienda (público) ----------

export const tienda = {
  menu: () => pedir("/api/tienda/menu"),
  estado: () => pedir("/api/tienda/estado"),
  // clave: una por intento de checkout. Si se reintenta con la misma, el backend
  // devuelve el pedido que ya había en vez de crear otro (mala señal en la cancha)
  crearPedido: (pedido, clave) =>
    pedir("/api/tienda/pedidos", { metodo: "POST", body: pedido, extra: clave ? { "Idempotency-Key": clave } : {} }),
  pedido: (codigo) => pedir(`/api/tienda/pedidos/${encodeURIComponent(codigo)}`),
};

export const pagos = {
  preferencia: (codigo) =>
    pedir(`/api/pagos/${encodeURIComponent(codigo)}/preferencia`, { metodo: "POST" }),
  verificar: (codigo) =>
    pedir(`/api/pagos/${encodeURIComponent(codigo)}/verificar`, { metodo: "POST" }),
};

// ---------- login y panel ----------

export const auth = {
  // Va como formulario: username (el email) y password
  login: (email, password) =>
    pedir("/api/auth/login", { metodo: "POST", form: { username: email, password } }),
  yo: () => pedir("/api/auth/yo", { conToken: true }),
};

export const panel = {
  pedidos: ({ todos = false } = {}) =>
    pedir(`/api/panel/pedidos${todos ? "?todos=true" : ""}`, { conToken: true }),
  resumen: () => pedir("/api/panel/resumen", { conToken: true }),
  cambiarEstado: (id, estado) =>
    pedir(`/api/panel/pedidos/${id}/estado`, { metodo: "PATCH", body: { estado }, conToken: true }),
  cobrar: (id) => pedir(`/api/panel/pedidos/${id}/cobrar`, { metodo: "POST", conToken: true }),
  cobrarYEntregar: (id) =>
    pedir(`/api/panel/pedidos/${id}/cobrar-y-entregar`, { metodo: "POST", conToken: true }),
  reimprimir: (id) =>
    pedir(`/api/panel/pedidos/${id}/reimprimir`, { metodo: "POST", conToken: true }),
};

// Atajos para las rutas del panel (todas con token)
const conToken = (ruta, opciones = {}) => pedir(ruta, { ...opciones, conToken: true });
const json = (metodo) => (ruta, body) => conToken(ruta, { metodo, body });
const post = json("POST");
const patch = json("PATCH");
const put = json("PUT");
const borrar = (ruta) => conToken(ruta, { metodo: "DELETE" });

// ---------- carta y precios (admin; prender y apagar también la cantina) ----------

export const carta = {
  ver: () => conToken("/api/carta"),
  crearCategoria: (datos) => post("/api/carta/categorias", datos),
  editarCategoria: (id, cambios) => patch(`/api/carta/categorias/${id}`, cambios),
  borrarCategoria: (id) => borrar(`/api/carta/categorias/${id}`),
  ordenarCategorias: (ids) => put("/api/carta/categorias/orden", { ids }),
  ordenarProductos: (categoriaId, ids) => put(`/api/carta/categorias/${categoriaId}/orden-productos`, { ids }),
  crearProducto: (datos) => post("/api/carta/productos", datos),
  editarProducto: (id, cambios) => patch(`/api/carta/productos/${id}`, cambios),
  borrarProducto: (id) => borrar(`/api/carta/productos/${id}`),
  disponibleProducto: (id, disponible) => patch(`/api/carta/productos/${id}/disponible`, { disponible }),
  subirFoto: (id, archivo) => {
    const form = new FormData();
    form.append("foto", archivo);
    return conToken(`/api/carta/productos/${id}/foto`, { metodo: "POST", archivo: form });
  },
  borrarFoto: (id) => borrar(`/api/carta/productos/${id}/foto`),
  crearGrupo: (productoId, datos) => post(`/api/carta/productos/${productoId}/grupos`, datos),
  editarGrupo: (id, cambios) => patch(`/api/carta/grupos/${id}`, cambios),
  borrarGrupo: (id) => borrar(`/api/carta/grupos/${id}`),
  crearOpcion: (grupoId, datos) => post(`/api/carta/grupos/${grupoId}/opciones`, datos),
  editarOpcion: (id, cambios) => patch(`/api/carta/opciones/${id}`, cambios),
  borrarOpcion: (id) => borrar(`/api/carta/opciones/${id}`),
  disponibleOpcion: (id, disponible) => patch(`/api/carta/opciones/${id}/disponible`, { disponible }),
  vistaPrevia: (datos) => post("/api/carta/aumento/vista-previa", datos),
  aplicarAumento: (datos) => post("/api/carta/aumento/aplicar", datos),
};

// ---------- configuración: horario, pausa, link de PedidosYa ----------

export const config = {
  ver: () => conToken("/api/config"),
  editar: (cambios) => patch("/api/config", cambios),
  horarios: (dias) => put("/api/config/horarios", { dias }),
  // La pausa la puede tocar también la cantina
  pausa: () => conToken("/api/config/pausa"),
  pausar: (pausado) => put("/api/config/pausa", { pausado }),
};

// ---------- usuarios (solo admin) ----------

export const usuarios = {
  lista: () => conToken("/api/auth/usuarios"),
  crear: (datos) => post("/api/auth/usuarios", datos),
  editar: (id, cambios) => patch(`/api/auth/usuarios/${id}`, cambios),
};

// ---------- caja del día ----------

export const caja = {
  // fecha "AAAA-MM-DD"; sin fecha, la jornada de hoy
  dia: (fecha) => conToken(`/api/panel/caja${fecha ? `?fecha=${encodeURIComponent(fecha)}` : ""}`),
  historial: (desde, hasta) => {
    const q = new URLSearchParams();
    if (desde) q.set("desde", desde);
    if (hasta) q.set("hasta", hasta);
    const texto = q.toString();
    return conToken(`/api/panel/caja/historial${texto ? `?${texto}` : ""}`);
  },
};

// ---------- WebSockets ----------

export const ws = {
  pedido: (codigo) => `${WS_URL}/ws/pedido/${encodeURIComponent(codigo)}`,
  panel: (token) => `${WS_URL}/ws/panel?token=${encodeURIComponent(token)}`,
};
