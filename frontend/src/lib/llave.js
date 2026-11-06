// La "llave" de cada intento de checkout (Idempotency-Key).
// Se guarda en sessionStorage: si el pedido no vuelve por mala señal y el
// cliente toca de nuevo, se manda la misma y el backend no crea otro pedido.
// Cuando el pedido entra bien, se borra y el próximo pedido lleva una nueva
import { CLAVES, sesion } from "./almacen";

function aleatoria() {
  // randomUUID solo existe con https o localhost. En la wifi local (http) no,
  // así que armo una igual de random con getRandomValues
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function llaveDelIntento() {
  let llave = sesion.leer(CLAVES.intento);
  if (!llave) {
    llave = aleatoria();
    sesion.guardar(CLAVES.intento, llave);
  }
  return llave;
}

export function olvidarIntento() {
  sesion.guardar(CLAVES.intento, null);
}
