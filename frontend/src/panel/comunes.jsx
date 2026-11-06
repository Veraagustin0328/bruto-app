import { useCallback, useEffect, useState } from "react";

// Piezas que usan todas las pantallas del panel

// ---------- avisitos de abajo ("Guardado", "Acordate de devolver el pago") ----------

export function useAvisos() {
  const [avisos, setAvisos] = useState([]);
  const avisar = useCallback((texto, tipo = "ok") => {
    const id = Math.random();
    setAvisos((a) => [...a, { id, texto, tipo }]);
    setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), tipo === "alerta" ? 9000 : 4000);
  }, []);
  return { avisos, avisar };
}

export function Avisos({ avisos }) {
  return (
    <div className="fixed bottom-4 inset-x-0 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none" aria-live="polite">
      {avisos.map((a) => (
        <div
          key={a.id}
          className={`max-w-md w-full rounded-xl px-4 py-3 text-sm font-semibold shadow-lg ${
            a.tipo === "alerta" ? "bg-alerta text-[#2a1d02]" : a.tipo === "error" ? "bg-naranja text-white" : "bg-gris text-texto"
          }`}
        >
          {a.texto}
        </div>
      ))}
    </div>
  );
}

// ---------- botones ----------

export function Boton({ children, secundario = false, peligro = false, grande = false, className = "", ...props }) {
  return (
    <button
      type="button"
      {...props}
      className={`font-semibold rounded-lg whitespace-nowrap disabled:opacity-50 ${grande ? "text-sm px-4 py-2.5" : "text-[13px] px-3 py-2"} ${
        peligro ? "bg-naranja/15 text-naranja" : secundario ? "bg-gris text-texto" : "bg-naranja text-white"
      } ${className}`}
    >
      {children}
    </button>
  );
}

// El interruptor verde de la maqueta (prendido = verde, apagado = gris)
export function Interruptor({ prendido, onCambiar, etiqueta, disabled = false, grande = false }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={prendido}
      aria-label={etiqueta}
      disabled={disabled}
      onClick={() => onCambiar(!prendido)}
      className={`relative flex-none rounded-full transition-colors disabled:opacity-50 ${grande ? "w-14 h-8" : "w-10 h-6"} ${
        prendido ? "bg-ok" : "bg-linea"
      }`}
    >
      <span
        className={`absolute top-1 rounded-full bg-white transition-all ${grande ? "w-6 h-6" : "w-4 h-4"} ${
          prendido ? (grande ? "left-7" : "left-5") : "left-1"
        }`}
      />
    </button>
  );
}

// "¿Seguro?" adentro de la página (nada de window.confirm)
export function Confirmar({ texto, si = "Sí", no = "No, dejalo", ocupado = false, onSi, onNo }) {
  return (
    <div role="alertdialog" className="rounded-xl bg-naranja/10 border border-naranja/40 p-3 grid gap-2.5">
      <p className="text-sm font-semibold">{texto}</p>
      <div className="flex gap-2 justify-end flex-wrap">
        <Boton secundario disabled={ocupado} onClick={onNo}>
          {no}
        </Boton>
        <Boton disabled={ocupado} onClick={onSi}>
          {ocupado ? "..." : si}
        </Boton>
      </div>
    </div>
  );
}

// ---------- en vivo / reconectando ----------

export function EnVivo({ conectado }) {
  return conectado ? (
    <span className="inline-flex items-center gap-1.5 text-ok font-semibold text-xs whitespace-nowrap">
      <span className="w-2 h-2 rounded-full bg-ok shadow-[0_0_0_3px_rgba(61,190,122,0.2)]" />
      En vivo
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-alerta font-semibold text-xs whitespace-nowrap">
      <span className="w-2 h-2 rounded-full bg-alerta animate-pulse" />
      Reconectando
    </span>
  );
}

// El cartel de arriba cuando se corta el WebSocket. Espera un segundo y medio
// antes de salir, así no parpadea al abrir la pantalla mientras conecta
export function AvisoConexion({ conectado, error, onReintentar, recargando = false }) {
  const [mostrar, setMostrar] = useState(false);
  useEffect(() => {
    if (conectado) {
      setMostrar(false);
      return undefined;
    }
    const t = setTimeout(() => setMostrar(true), 1500);
    return () => clearTimeout(t);
  }, [conectado]);

  const cortado = !conectado && mostrar;
  if (!cortado && !error) return null;
  return (
    <div
      role="alert"
      className={`sticky top-0 z-40 px-4 py-3 flex items-center justify-between gap-3 font-semibold shadow-lg ${
        cortado ? "bg-alerta text-[#2a1d02]" : "bg-naranja text-white"
      }`}
    >
      <span className="flex items-center gap-2.5">
        {cortado && <span className="w-3 h-3 flex-none rounded-full bg-[#2a1d02] animate-pulse" />}
        <span>
          {cortado ? (
            <>
              <b className="block text-base md:text-lg leading-tight">Sin conexión, reconectando...</b>
              <small className="text-[12.5px] font-medium">Los pedidos nuevos pueden tardar en aparecer. Cuando vuelva, suenan los que entraron.</small>
            </>
          ) : (
            `No pudimos traer los datos: ${error}`
          )}
        </span>
      </span>
      {onReintentar && (
        <button
          type="button"
          onClick={onReintentar}
          disabled={recargando}
          className="underline whitespace-nowrap text-sm disabled:no-underline disabled:opacity-70"
        >
          {recargando ? "Recargando..." : "Recargar"}
        </button>
      )}
    </div>
  );
}

export function AvisoSonido({ habilitado }) {
  if (habilitado) return null;
  return (
    <button type="button" className="w-full bg-naranja text-white text-sm font-semibold px-4 py-2">
      🔔 Tocá acá para activar el sonido de pedidos nuevos
    </button>
  );
}

// Título de cada pantalla del panel
export function Titulo({ children, bajada, derecha }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 px-4 md:px-6 pt-5">
      <div className="grid gap-1">
        <h1 className="text-[30px] md:text-[34px]">{children}</h1>
        {bajada && <p className="text-tenue text-[13px] max-w-[70ch]">{bajada}</p>}
      </div>
      {derecha}
    </div>
  );
}

// Para los "cargando" de listas
export function Esqueleto({ alto = "h-40", className = "" }) {
  return <div className={`${alto} rounded-2xl bg-negro border border-gris animate-pulse ${className}`} aria-label="Cargando" />;
}

// true si la pantalla es al menos así de ancha (para no renderizar dos veces lo mismo)
export function useAncho(minimo) {
  const consulta = `(min-width: ${minimo}px)`;
  const [si, setSi] = useState(() => window.matchMedia?.(consulta).matches ?? true);
  useEffect(() => {
    const m = window.matchMedia?.(consulta);
    if (!m) return undefined;
    const alCambiar = () => setSi(m.matches);
    m.addEventListener("change", alCambiar);
    return () => m.removeEventListener("change", alCambiar);
  }, [consulta]);
  return si;
}
