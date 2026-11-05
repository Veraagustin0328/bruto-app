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

  const valor = useMemo(() => {
    const cantidad = items.reduce((s, i) => s + i.cantidad, 0);
    const total = items.reduce((s, i) => s + i.precio_unitario * i.cantidad, 0);
    return { items, cantidad, total, agregar, cambiarCantidad, quitar, vaciar, MAX_CANTIDAD };
  }, [items, agregar, cambiarCantidad, quitar, vaciar]);

  return <CarritoContext.Provider value={valor}>{children}</CarritoContext.Provider>;
}

export function useCarrito() {
  const ctx = useContext(CarritoContext);
  if (!ctx) throw new Error("useCarrito va adentro de <CarritoProvider>");
  return ctx;
}
