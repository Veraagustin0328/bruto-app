import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { CLAVES, local } from "../lib/almacen";

// El carrito vive en un contexto y se guarda en localStorage,
// así no se pierde si recarga la página o se le cierra el navegador.
// Ojo: los precios de acá son solo para mostrar. El que vale es el del backend

const CarritoContext = createContext(null);

// Un carrito de hace más de 6 horas ya es de otro partido: lo tiramos
const VENCE_MS = 6 * 60 * 60 * 1000;
const MAX_CANTIDAD = 20; // el backend acepta hasta 20 de cada item

function cargar() {
  const guardado = local.leer(CLAVES.carrito);
  if (!guardado || !Array.isArray(guardado.items)) return [];
  if (Date.now() - (guardado.guardado || 0) > VENCE_MS) return [];
  return guardado.items.filter((i) => i && i.producto_id && i.cantidad > 0);
}

// Dos items son "el mismo" si tienen mismo producto, mismas opciones y misma nota
function claveDe(item) {
  const opciones = [...item.opciones]
    .sort((a, b) => a.opcion_id - b.opcion_id)
    .map((o) => `${o.opcion_id}x${o.cantidad}`)
    .join(",");
  return `${item.producto_id}|${opciones}|${(item.nota || "").trim().toLowerCase()}`;
}

// Pone el carrito al día con la carta de ahora: precios (si Renzo aumentó en el
// medio) y lo que se apagó. No toca nada si no cambió. Los items con problema
// quedan marcados con `problema` (texto para el cliente) y no se pueden mandar
export function repasarConCarta(items, menu) {
  const productos = new Map();
  for (const cat of menu) for (const p of cat.productos) productos.set(p.id, p);

  return items.map((item) => {
    const prod = productos.get(item.producto_id);
    if (!prod) return { ...item, problema: "Ya no está en la carta" };
    if (!prod.disponible) return { ...item, nombre: prod.nombre, problema: "Hoy no hay" };

    const opciones = new Map();
    for (const g of prod.grupos) for (const o of g.opciones) opciones.set(o.id, o);
    let unitario = Number(prod.precio);
    let problema = null;
    const ops = item.opciones.map((o) => {
      const actual = opciones.get(o.opcion_id);
      if (!actual) {
        problema = problema || `${o.nombre} ya no está`;
        return o;
      }
      if (!actual.disponible) problema = problema || `Hoy no hay ${actual.nombre.toLowerCase()}`;
      unitario += Number(actual.precio_extra) * o.cantidad;
      return { ...o, nombre: actual.nombre, precio_extra: Number(actual.precio_extra) };
    });

    const sig = { ...item, nombre: prod.nombre, opciones: ops, precio_unitario: unitario, problema };
    if (!problema) delete sig.problema;
    return sig;
  });
}

export function CarritoProvider({ children }) {
  const [items, setItems] = useState(cargar);

  useEffect(() => {
    local.guardar(CLAVES.carrito, items.length ? { items, guardado: Date.now() } : null);
  }, [items]);

  const agregar = useCallback((nuevo) => {
    setItems((actuales) => {
      const clave = claveDe(nuevo);
      const igual = actuales.find((i) => claveDe(i) === clave);
      if (igual) {
        return actuales.map((i) =>
          i === igual ? { ...i, cantidad: Math.min(MAX_CANTIDAD, i.cantidad + nuevo.cantidad) } : i,
        );
      }
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      return [...actuales, { ...nuevo, id }];
    });
  }, []);

  const cambiarCantidad = useCallback((id, cantidad) => {
    setItems((actuales) =>
      cantidad <= 0
        ? actuales.filter((i) => i.id !== id)
        : actuales.map((i) => (i.id === id ? { ...i, cantidad: Math.min(MAX_CANTIDAD, cantidad) } : i)),
    );
  }, []);

  const quitar = useCallback((id) => setItems((a) => a.filter((i) => i.id !== id)), []);
  const vaciar = useCallback(() => setItems([]), []);

  // Repasa el carrito con la carta de ahora. Devuelve cuántos precios cambiaron
  const repasar = useCallback(
    (menu) => {
      const nuevos = repasarConCarta(items, menu);
      const cambiaron = nuevos.filter((n, i) => n.precio_unitario !== items[i].precio_unitario).length;
      if (JSON.stringify(nuevos) !== JSON.stringify(items)) setItems(nuevos);
      return cambiaron;
    },
    [items],
  );

  const valor = useMemo(() => {
    const cantidad = items.reduce((s, i) => s + i.cantidad, 0);
    // Lo que hoy no hay no suma: igual hay que sacarlo para poder seguir
    const total = items.reduce((s, i) => (i.problema ? s : s + i.precio_unitario * i.cantidad), 0);
    const conProblema = items.filter((i) => i.problema);
    return { items, cantidad, total, conProblema, agregar, cambiarCantidad, quitar, vaciar, repasar, MAX_CANTIDAD };
  }, [items, agregar, cambiarCantidad, quitar, vaciar, repasar]);

  return <CarritoContext.Provider value={valor}>{children}</CarritoContext.Provider>;
}

export function useCarrito() {
  const ctx = useContext(CarritoContext);
  if (!ctx) throw new Error("useCarrito va adentro de <CarritoProvider>");
  return ctx;
}
