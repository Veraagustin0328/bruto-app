import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { panel } from "../api";
import { fecha, numeroPedido, reloj, textoOpciones } from "../lib/formato";
import useSonido from "../lib/sonido";
import { AvisoConexion, AvisoSonido, EnVivo } from "./Panel";
import { useSalir } from "./sesion";
import usePedidosEnVivo, { useAhora } from "./usePedidosEnVivo";

// Pantalla de la cocina (parte 3 de la maqueta), para una tablet acostada:
// letra grande, solo lo que hay que cocinar y un botón por comanda

const EN_COCINA = ["recibido", "en_preparacion"];
const TARDE_SEG = 12 * 60; // a los 12 minutos el reloj se pone amarillo

// Que la pantalla de la tablet no se apague (si el navegador deja)
function usePantallaPrendida() {
  const [prendida, setPrendida] = useState(false);
  useEffect(() => {
    if (!("wakeLock" in navigator)) return undefined;
    let lock = null;
    let terminado = false;

    async function pedir() {
      try {
        lock = await navigator.wakeLock.request("screen");
        if (terminado) {
          lock.release();
          return;
        }
        setPrendida(true);
        lock.addEventListener("release", () => setPrendida(false));
      } catch {
        // sin batería o el navegador no quiso: seguimos igual
      }
    }
    // El lock se suelta solo cuando la pestaña queda atrás; al volver lo pido de nuevo
    const alVolver = () => document.visibilityState === "visible" && pedir();
    pedir();
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      terminado = true;
      document.removeEventListener("visibilitychange", alVolver);
      lock?.release().catch(() => {});
    };
  }, []);
  return prendida;
}

function Comanda({ p, nuevo, ahora, onActualizado }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const enCurso = useRef(false);

  const segundos = (ahora - fecha(p.created_at).getTime()) / 1000;
  const tarde = segundos >= TARDE_SEG;
  const recien = nuevo || segundos < 60;
  const siguiente = p.estado === "recibido" ? "en_preparacion" : "listo";

  async function avanzar() {
    if (enCurso.current) return;
    enCurso.current = true;
    setOcupado(true);
    setError(null);
    try {
      onActualizado(await panel.cambiarEstado(p.id, siguiente));
    } catch (e) {
      setError(e.message);
    } finally {
      enCurso.current = false;
      setOcupado(false);
    }
  }

  return (
    <article className={`bg-carbon rounded-2xl overflow-hidden border flex flex-col ${recien ? "border-naranja" : "border-gris"}`}>
      <div
        className={`px-4 py-2.5 flex justify-between items-center ${
          tarde ? "bg-alerta/20" : recien ? "bg-naranja" : "bg-gris"
        }`}
      >
        <b className="font-display font-normal text-[36px] leading-none num">{numeroPedido(p.numero)}</b>
        <time className={`font-bold text-lg num ${tarde ? "text-alerta" : ""}`}>{reloj(segundos)}</time>
      </div>
      <div className="px-4 pt-2.5 text-[13px] font-bold tracking-wider uppercase text-tenue">
        {p.modo === "comer_adentro" ? `Adentro · ${p.ubicacion}` : `Take away · ${p.nombre}`}
      </div>
      <ul className="px-4 pt-2 pb-3 grid gap-2.5 flex-1">
        {p.items.map((it, i) => (
          <li key={i} className="text-[20px] font-semibold leading-tight">
            <em className="not-italic text-naranja mr-1 num">{it.cantidad}×</em>
            {it.nombre_producto}
            {it.opciones.length > 0 && (
              <small className="block text-[15px] font-medium text-tenue mt-0.5">+ {textoOpciones(it.opciones)}</small>
            )}
            {it.nota && <small className="block text-[15px] font-bold text-alerta mt-0.5 uppercase">{it.nota}</small>}
          </li>
        ))}
        {p.notas && <li className="text-[15px] font-bold text-alerta uppercase">Nota: {p.notas}</li>}
      </ul>
      {error && <p className="px-4 pb-2 text-naranja text-sm">{error}</p>}
      <button
        type="button"
        onClick={avanzar}
        disabled={ocupado}
        className={`mx-3 mb-3 py-4 rounded-xl font-bold text-lg tracking-wider disabled:opacity-60 ${
          p.estado === "recibido" ? "bg-naranja text-white" : "bg-ok text-[#062814]"
        }`}
      >
        {ocupado ? "..." : p.estado === "recibido" ? "EMPEZAR" : "LISTO"}
      </button>
    </article>
  );
}

export default function Cocina({ sesion }) {
  const salir = useSalir();
  const { sonar, habilitado } = useSonido();
  const ahora = useAhora(1000);
  const prendida = usePantallaPrendida();
  const { lista, cargando, error, conectado, recargar, actualizar, destacados } = usePedidosEnVivo(sesion.token, EN_COCINA, {
    onNuevo: sonar,
  });

  const horaActual = new Date(ahora).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });

  return (
    <div className="min-h-dvh bg-negro">
      <AvisoConexion conectado={conectado} error={error} onReintentar={recargar} />
      <AvisoSonido habilitado={habilitado} />

      <header className="flex justify-between items-center gap-4 px-5 md:px-6 py-3.5 border-b border-gris">
        <h1 className="text-[32px]">
          Cocina <span className="text-naranja">· {lista.length} en marcha</span>
        </h1>
        <div className="flex items-center gap-4 text-[13px] text-tenue">
          <span className="font-semibold text-texto text-lg num">{horaActual}</span>
          <EnVivo conectado={conectado} />
          {!prendida && "wakeLock" in navigator && <span className="hidden md:inline text-alerta text-xs">La pantalla se puede apagar</span>}
          {sesion.usuario.rol !== "cocina" && (
            <Link to="/panel" className="hover:text-texto">
              Panel
            </Link>
          )}
          <button type="button" onClick={salir} className="hover:text-texto">
            Salir
          </button>
        </div>
      </header>

      <main className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-4 md:p-6 items-start">
        {cargando ? (
          [0, 1, 2].map((i) => <div key={i} className="h-64 rounded-2xl bg-carbon animate-pulse" />)
        ) : lista.length === 0 ? (
          <p className="col-span-full text-center text-tenue text-xl py-24 font-display tracking-wide">
            Nada en la plancha. Cuando entre un pedido aparece acá.
          </p>
        ) : (
          lista.map((p) => <Comanda key={p.id} p={p} nuevo={destacados.has(p.id)} ahora={ahora} onActualizado={actualizar} />)
        )}
      </main>
    </div>
  );
}
