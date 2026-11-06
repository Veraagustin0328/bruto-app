// Formatos que se repiten en toda la app

const numeros = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });

// 12500 → "$12.500"
export function precio(n) {
  return `$${numeros.format(Math.round(Number(n) || 0))}`;
}

// 42 → "#042"
export function numeroPedido(n) {
  return `#${String(n).padStart(3, "0")}`;
}

// "00:30:00" → "00:30"
export function hora(hhmmss) {
  return (hhmmss || "").slice(0, 5);
}

// El backend manda fechas con zona ("...-03:00" o "Z"). Si alguna viene sin zona
// (pasa con SQLite) es UTC: sin esto el navegador la tomaría como hora local
export function fecha(iso) {
  if (!iso) return null;
  const conZona = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(conZona ? iso : `${iso}Z`);
}

// Fecha ISO → "21:45" en la hora de Mendoza
export function horaDe(iso) {
  if (!iso) return "";
  return fecha(iso).toLocaleTimeString("es-AR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Argentina/Mendoza",
  });
}

// Minutos desde una fecha ISO hasta ahora
export function minutosDesde(iso, ahora = Date.now()) {
  return Math.max(0, Math.floor((ahora - fecha(iso).getTime()) / 60000));
}

// "recién", "hace 16 min", "hace 1 h 5 min"
export function haceCuanto(iso, ahora = Date.now()) {
  const min = minutosDesde(iso, ahora);
  if (min < 1) return "recién";
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  const resto = min % 60;
  return resto ? `hace ${h} h ${resto} min` : `hace ${h} h`;
}

// Segundos → "07:14" (el reloj de la cocina)
export function reloj(segundos) {
  const s = Math.max(0, Math.floor(segundos));
  const m = Math.floor(s / 60);
  const dos = (x) => String(x).padStart(2, "0");
  if (m >= 60) return `${Math.floor(m / 60)}:${dos(m % 60)}:${dos(s % 60)}`;
  return `${dos(m)}:${dos(s % 60)}`;
}

// "2615550142" → "261 555 0142", solo para que se lea mejor
export function telefono(t) {
  const d = String(t || "").replace(/\D/g, "");
  if (d.length === 10) return `${d.slice(0, 3)} ${d.slice(3, 6)} ${d.slice(6)}`;
  return d;
}

// Opciones de un item → "Doble · 2× Extra carne y queso"
export function textoOpciones(opciones = []) {
  return opciones
    .map((o) => {
      const nombre = o.nombre_opcion ?? o.nombre;
      return o.cantidad > 1 ? `${o.cantidad}× ${nombre}` : nombre;
    })
    .join(" · ");
}

// Lo que escribe Renzo en un precio → número. Acepta "13.500", "13500",
// "$ 13.500", "2,5". Devuelve NaN si no se entiende
export function leerPrecio(texto) {
  let t = String(texto ?? "").replace(/[$\s]/g, "");
  if (!t) return NaN;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
  return /^\d+(\.\d{1,2})?$/.test(t) ? Number(t) : NaN;
}
