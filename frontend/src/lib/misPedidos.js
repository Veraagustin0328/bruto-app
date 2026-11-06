// Los últimos pedidos que hizo este celu, para el "Ver mi pedido" de la carta.
// Se guardan los códigos de las últimas 12 horas (hasta 5)
import { CLAVES, local } from "./almacen";

const VALE_MS = 12 * 60 * 60 * 1000;
const MAX = 5;

export function misPedidos() {
  const lista = local.leer(CLAVES.misPedidos, []);
  const viejo = local.leer(CLAVES.ultimoPedido); // lo que guardaba la versión anterior
  const todos = Array.isArray(lista) ? [...lista] : [];
  if (viejo?.codigo && !todos.some((p) => p.codigo === viejo.codigo)) todos.push(viejo);
  return todos.filter((p) => p?.codigo && Date.now() - (p.creado || 0) < VALE_MS);
}

export function recordarPedido(codigo) {
  if (!codigo) return;
  const resto = misPedidos().filter((p) => p.codigo !== codigo);
  local.guardar(CLAVES.misPedidos, [{ codigo, creado: Date.now() }, ...resto].slice(0, MAX));
  local.guardar(CLAVES.ultimoPedido, null);
}

export function olvidarPedido(codigo) {
  local.guardar(
    CLAVES.misPedidos,
    misPedidos().filter((p) => p.codigo !== codigo),
  );
}
