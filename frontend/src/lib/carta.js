// Ayudas para leer la carta que manda el backend

// El grupo "Tamaño" (Simple / Doble) de una burger, si tiene
export function grupoTamanio(producto) {
  return producto.grupos?.find(
    (g) => g.tipo === "unica" && g.nombre.toLowerCase().startsWith("tama"),
  );
}

// Precio del doble para mostrar en la carta, o null si no tiene
export function precioDoble(producto) {
  const grupo = grupoTamanio(producto);
  const doble = grupo?.opciones.find((o) => o.nombre.toLowerCase() === "doble");
  return doble ? Number(producto.precio) + Number(doble.precio_extra) : null;
}

// Opción con stepper (− 2 +) o de un solo toque
export function usaStepper(opcion) {
  return opcion.cantidad_max === null || opcion.cantidad_max > 1;
}

// El backend acepta hasta 10 de cada opción
export function topeOpcion(opcion) {
  return Math.min(opcion.cantidad_max ?? 10, 10);
}
