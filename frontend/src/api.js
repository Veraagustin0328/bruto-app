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

async function pedir(ruta, { metodo = "GET", body, form, conToken = false } = {}) {
  const headers = {};
  let cuerpo;

  if (form) {
    cuerpo = new URLSearchParams(form);
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
  crearPedido: (pedido) => pedir("/api/tienda/pedidos", { metodo: "POST", body: pedido }),
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

// ---------- WebSockets ----------

export const ws = {
  pedido: (codigo) => `${WS_URL}/ws/pedido/${encodeURIComponent(codigo)}`,
  panel: (token) => `${WS_URL}/ws/panel?token=${encodeURIComponent(token)}`,
};
