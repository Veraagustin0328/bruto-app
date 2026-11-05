import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { tienda } from "../api";
import Logo from "../componentes/Logo";
import { CLAVES, local } from "../lib/almacen";
import { hora, numeroPedido, precio } from "../lib/formato";
import { Carta, EsqueletoCarta } from "./Carta";
import Checkout from "./Checkout";
import HojaProducto from "./HojaProducto";
import { useCarrito } from "./carrito";

// Arriba a la derecha: "Cantina abierta hasta las 00:30" o "Cerrada"
function EstadoCantina({ estado }) {
  if (!estado) return null;
  if (estado.acepta_pedidos) {
    return (
      <div className="text-[11.5px] text-tenue text-right leading-tight">
        Cantina abierta
        {estado.horario_hoy && (
          <b className="block text-texto font-semibold">hasta las {hora(estado.horario_hoy.cierra)}</b>
        )}
      </div>
    );
  }
  return (
    <div className="text-[11.5px] text-right leading-tight">
      <b className="block text-alerta font-semibold">{estado.pausado ? "Pedidos en pausa" : "Cantina cerrada"}</b>
    </div>
  );
}

export function Cabecera({ estado }) {
  return (
    <header className="flex items-center justify-between px-4 pt-3 pb-1">
      <Logo />
      <EstadoCantina estado={estado} />
    </header>
  );
}

// Si tiene un pedido en curso de hace poco, un acceso para volver a verlo
const ULTIMO_VALE_MS = 12 * 60 * 60 * 1000;
const NOMBRE_ESTADO = {
  pendiente_pago: "esperando el pago",
  recibido: "recibido",
  en_preparacion: "en la plancha",
  listo: "listo",
};

function UltimoPedido() {
  const [pedido, setPedido] = useState(null);

  useEffect(() => {
    const ultimo = local.leer(CLAVES.ultimoPedido);
    if (!ultimo?.codigo || Date.now() - (ultimo.creado || 0) > ULTIMO_VALE_MS) return;
    tienda
      .pedido(ultimo.codigo)
      .then((p) => {
        if (NOMBRE_ESTADO[p.estado]) setPedido(p);
        else local.guardar(CLAVES.ultimoPedido, null); // ya terminó: no lo muestro más
      })
      .catch(() => {});
  }, []);

  if (!pedido) return null;
  return (
    <Link
      to={`/pedido/${pedido.codigo}`}
      className="mx-4 mt-2 mb-1 flex items-center justify-between gap-3 rounded-xl border border-naranja/50 bg-naranja/10 px-3.5 py-2.5 text-sm"
    >
      <span>
        Tu pedido <b className="num">{numeroPedido(pedido.numero)}</b> está {NOMBRE_ESTADO[pedido.estado]}
      </span>
      <span className="text-naranja font-semibold whitespace-nowrap">Ver mi pedido ›</span>
    </Link>
  );
}

export function ErrorConReintento({ mensaje, onReintentar }) {
  return (
    <div className="mx-4 mt-10 p-5 rounded-2xl bg-carbon border border-linea text-center flex flex-col gap-3 items-center">
      <p className="font-display text-2xl">No pudimos cargar la carta</p>
      <p className="text-tenue text-sm">{mensaje}</p>
      <button
        type="button"
        onClick={onReintentar}
        className="mt-1 px-5 py-2.5 rounded-xl bg-naranja text-white font-semibold"
      >
        Reintentar
      </button>
    </div>
  );
}

// La barra naranja de abajo: "Ver mi pedido · 2 · $29.000"
function BarraCarrito({ onVer }) {
  const { cantidad, total } = useCarrito();
  if (!cantidad) return null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 pointer-events-none">
      <div className="max-w-[560px] mx-auto px-3 pb-[max(14px,env(safe-area-inset-bottom))]">
        <button
          type="button"
          onClick={onVer}
          className="pointer-events-auto w-full flex items-center justify-between rounded-2xl bg-naranja text-white font-semibold px-4 py-3.5 shadow-[0_8px_22px_rgba(240,92,43,0.35)] num"
        >
          <span className="flex items-center">
            <span className="bg-black/25 rounded-md px-2 mr-2.5">{cantidad}</span>
            Ver mi pedido
          </span>
          <span>{precio(total)}</span>
        </button>
      </div>
    </div>
  );
}

export default function Tienda() {
  const [menu, setMenu] = useState(null);
  const [estado, setEstado] = useState(null);
  const [error, setError] = useState(null);
  const [abierto, setAbierto] = useState(null); // producto en la hoja de abajo
  const { agregar } = useCarrito();
  const cerrarHoja = useCallback(() => setAbierto(null), []);

  // El checkout va en la misma página con ?paso=pedido / ?paso=datos,
  // así el botón "atrás" del celu anda. ?donde=Cancha 3 viene del QR de la cancha
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const paso = ["pedido", "datos"].includes(params.get("paso")) ? params.get("paso") : null;
  const donde = (params.get("donde") || "").trim().slice(0, 120);

  function irA(destino) {
    const sig = new URLSearchParams(params);
    if (destino) sig.set("paso", destino);
    else sig.delete("paso");
    const pasos = [null, "pedido", "datos"];
    const vuelve = pasos.indexOf(destino) < pasos.indexOf(paso);
    // Volver: si hay historia nuestra, uso el atrás del navegador; si no, reemplazo
    if (vuelve && location.key !== "default") navigate(-1);
    else setParams(sig, { replace: vuelve });
  }

  const cargar = useCallback(async () => {
    setError(null);
    setMenu(null);
    try {
      setMenu(await tienda.menu());
    } catch (e) {
      setError(e.message);
    }
    // El estado (abierto/cerrado) no es vital: si falla, la carta se ve igual
    tienda.estado().then(setEstado).catch(() => {});
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const cabecera = <Cabecera estado={estado} />;
  const avisos = (
    <>
      {estado && !estado.acepta_pedidos && estado.mensaje && (
        <p className="mx-4 mt-2 p-3 rounded-xl bg-alerta/15 text-alerta text-sm">{estado.mensaje}</p>
      )}
      <UltimoPedido />
    </>
  );

  if (paso) {
    return (
      <div className="max-w-[560px] mx-auto min-h-dvh">
        <Checkout paso={paso} irA={irA} donde={donde} estadoTienda={estado} />
      </div>
    );
  }

  return (
    <div className="max-w-[560px] mx-auto min-h-dvh">
      {error ? (
        <>
          {cabecera}
          {avisos}
          <ErrorConReintento mensaje={error} onReintentar={cargar} />
        </>
      ) : !menu ? (
        <>
          {cabecera}
          {avisos}
          <EsqueletoCarta />
        </>
      ) : (
        <Carta categorias={menu} arriba={cabecera} avisos={avisos} onElegir={setAbierto} />
      )}

      <BarraCarrito onVer={() => irA("pedido")} />

      {abierto && (
        <HojaProducto
          producto={abierto}
          onCerrar={cerrarHoja}
          onAgregar={(item) => {
            agregar(item);
            setAbierto(null);
          }}
        />
      )}
    </div>
  );
}
