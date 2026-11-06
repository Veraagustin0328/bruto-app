// localStorage y sessionStorage con try/catch: en incógnito o con el
// storage lleno tiran error, y no queremos que se caiga la app por eso

function leer(tipo, clave, porDefecto) {
  try {
    const crudo = window[tipo].getItem(clave);
    return crudo === null ? porDefecto : JSON.parse(crudo);
  } catch {
    return porDefecto;
  }
}

function guardar(tipo, clave, valor) {
  try {
    if (valor === undefined || valor === null) window[tipo].removeItem(clave);
    else window[tipo].setItem(clave, JSON.stringify(valor));
  } catch {
    // sin storage: seguimos igual, solo que no se acuerda
  }
}

export const local = {
  leer: (clave, porDefecto = null) => leer("localStorage", clave, porDefecto),
  guardar: (clave, valor) => guardar("localStorage", clave, valor),
};

export const sesion = {
  leer: (clave, porDefecto = null) => leer("sessionStorage", clave, porDefecto),
  guardar: (clave, valor) => guardar("sessionStorage", clave, valor),
};

// Todas las claves juntas, así no se pisan
export const CLAVES = {
  carrito: "bruto.carrito",
  datos: "bruto.datos",
  ultimoPedido: "bruto.ultimo-pedido",
  intro: "bruto.intro",
  intento: "bruto.intento", // Idempotency-Key del checkout en curso
};
