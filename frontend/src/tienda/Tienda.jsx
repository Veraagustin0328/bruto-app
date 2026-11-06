import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { tienda } from "../api";
import Logo from "../componentes/Logo";
import { CLAVES, sesion } from "../lib/almacen";
import { hora, numeroPedido, precio } from "../lib/formato";
import { misPedidos, olvidarPedido } from "../lib/misPedidos";
import { Carta, EsqueletoCarta } from "./Carta";
import Checkout from "./Checkout";
import HojaProducto from "./HojaProducto";
import IntroBruto from "./IntroBruto";
import { useCarrito } from "./carrito";
import useEstadoTienda from "./useEstadoTienda";

// Arriba a la derecha: "Cantina abierta hasta las 00:30", "Cerrada" o "En pausa"
function EstadoCantina({ estado, fallo }) {
  if (!estado) {
    return fallo ? (
      <div className="text-[11.5px] text-tenue text-right leading-tight max-w-36">No pudimos ver si la cantina está abierta</div>
    ) : null;
  }
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
      <b className="block text-alerta font-semibold">{estado.pausado && estado.abierto ? "Pedidos en pausa" : "Cantina cerrada"}</b>
    </div>
  );
}

export function Cabecera({ estado, fallo }) {
  return (
    <header className="flex items-center justify-between px-4 pt-3 pb-1">
      <Logo />
      <EstadoCantina estado={estado} fallo={fallo} />
    </header>
  );
}

// Si tiene pedidos en curso de hace poco, un acceso a cada uno
const NOMBRE_ESTADO = {
  pendiente_pago: "esperando el pago",
  recibido: "recibido",
  en_preparacion: "en la plancha",
  listo: "listo",
};

function MisPedidos() {
  const [pedidos, setPedidos] = useState([]);

  useEffect(() => {
    let vivo = true;
    Promise.all(
      misPedidos().map((m) =>
        tienda
          .pedido(m.codigo)
          .then((p) => {
            if (NOMBRE_ESTADO[p.estado]) return p;
            olvidarPedido(m.codigo); // ya terminó: no lo muestro más
            return null;
          })
          .catch(() => null),
      ),
    ).then((lista) => vivo && setPedidos(lista.filter(Boolean).sort((a, b) => a.numero - b.numero)));
    return () => {
      vivo = false;
    };
  }, []);

  return pedidos.map((pedido) => (
    <Link
      key={pedido.codigo}
      to={`/pedido/${pedido.codigo}`}
      className="mx-4 mt-2 mb-1 flex items-center justify-between gap-3 rounded-xl border border-naranja/50 bg-naranja/10 px-3.5 py-2.5 text-sm"
    >
      <span>
        Tu pedido <b className="num">{numeroPedido(pedido.numero)}</b> está {NOMBRE_ESTADO[pedido.estado]}
      </span>
      <span className="text-naranja font-semibold whitespace-nowrap">Ver mi pedido ›</span>
    </Link>
  ));
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
  const [error, setError] = useState(null);
  const { estado, fallo } = useEstadoTienda();
  const { agregar } = useCarrito();

  // El checkout va en la misma página con ?paso=pedido / ?paso=datos, y la hoja
  // del producto con ?ver=<id>: así el botón "atrás" del celu vuelve un paso o
  // cierra la hoja. ?donde=Cancha 3 viene del QR de la cancha
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const paso = ["pedido", "datos"].includes(params.get("paso")) ? params.get("paso") : null;
  const donde = (params.get("donde") || "").trim().slice(0, 120);
  const verId = Number(params.get("ver")) || null;

  // La intro sale una sola vez por visita, y no si entra directo al checkout
  const [verIntro, setVerIntro] = useState(() => !paso && !verId && !sesion.leer(CLAVES.intro));
  useEffect(() => {
    if (verIntro) sesion.guardar(CLAVES.intro, 1);
  }, [verIntro]);
  const terminarIntro = useCallback(() => setVerIntro(false), []);

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

  // El producto abierto en la hoja (solo si existe y se puede pedir)
  const abierto = useMemo(() => {
    if (!verId || !menu) return null;
    for (const c of menu) {
      const p = c.productos.find((x) => x.id === verId);
      if (p) return p.disponible ? p : null;
    }
    return null;
  }, [verId, menu]);

  const abrirHoja = useCallback(
    (producto) => {
      const sig = new URLSearchParams(params);
      sig.set("ver", producto.id);
      setParams(sig, { state: { hoja: true } });
    },
    [params, setParams],
  );

  const cerrarHoja = useCallback(() => {
    // Si la abrimos nosotros, "atrás" (así no queda en el historial); si vino
    // con ?ver= en el link, saco el parámetro
    if (location.state?.hoja) navigate(-1);
    else {
      const sig = new URLSearchParams(params);
      sig.delete("ver");
      setParams(sig, { replace: true });
    }
  }, [location.state, navigate, params, setParams]);

  const cargar = useCallback(async () => {
    setError(null);
    setMenu(null);
    try {
      setMenu(await tienda.menu());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const cabecera = <Cabecera estado={estado} fallo={fallo} />;
  const avisos = (
    <>
      {estado && !estado.acepta_pedidos && estado.mensaje && (
        <p className="mx-4 mt-2 p-3 rounded-xl bg-alerta/15 text-alerta text-sm">{estado.mensaje}</p>
      )}
      <MisPedidos />
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
        <Carta categorias={menu} arriba={cabecera} avisos={avisos} onElegir={abrirHoja} />
      )}

      <BarraCarrito onVer={() => irA("pedido")} />

      {verIntro && <IntroBruto donde={donde} onTerminar={terminarIntro} />}

      {abierto && (
        <HojaProducto
          key={abierto.id}
          producto={abierto}
          onCerrar={cerrarHoja}
          onAgregar={(item) => {
            agregar(item);
            cerrarHoja();
          }}
        />
      )}
    </div>
  );
}
