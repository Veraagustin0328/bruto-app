import { useCallback, useEffect, useState } from "react";
import { tienda } from "../api";
import Logo from "../componentes/Logo";
import { hora, precio } from "../lib/formato";
import { Carta, EsqueletoCarta } from "./Carta";
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

  return (
    <div className="max-w-[560px] mx-auto min-h-dvh">
      {error ? (
        <>
          {cabecera}
          <ErrorConReintento mensaje={error} onReintentar={cargar} />
        </>
      ) : !menu ? (
        <>
          {cabecera}
          <EsqueletoCarta />
        </>
      ) : (
        <Carta categorias={menu} arriba={cabecera} onElegir={setAbierto} />
      )}

      <BarraCarrito onVer={() => {}} />

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
