import { useCallback, useEffect, useState } from "react";
import { tienda } from "../api";
import Logo from "../componentes/Logo";
import { hora } from "../lib/formato";
import { Carta, EsqueletoCarta } from "./Carta";

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

export default function Tienda() {
  const [menu, setMenu] = useState(null);
  const [estado, setEstado] = useState(null);
  const [error, setError] = useState(null);

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
        <Carta categorias={menu} arriba={cabecera} />
      )}
    </div>
  );
}
