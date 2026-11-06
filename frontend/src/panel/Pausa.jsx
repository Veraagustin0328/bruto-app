import { useCallback, useEffect, useState } from "react";
import { config as api } from "../api";

// El interruptor de "Pausar pedidos" (botón de pánico para cuando la cocina
// explota). Lo usan la cantina y el admin. `version` sube cuando llega
// "config_actualizada" por el WebSocket, así si lo toca otro se ve acá
export default function Pausa({ version = 0, avisar, grande = false }) {
  const [datos, setDatos] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);

  const cargar = useCallback(() => {
    api
      .pausa()
      .then((d) => {
        setDatos(d);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar, version]);

  async function cambiar() {
    if (!datos || ocupado) return;
    const valor = !datos.pedidos_pausados;
    setOcupado(true);
    setError(null);
    try {
      setDatos(await api.pausar(valor));
      avisar?.(valor ? "Pedidos en pausa: la tienda no toma pedidos nuevos" : "Listo, la tienda toma pedidos de nuevo", valor ? "alerta" : "ok");
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  const pausado = datos?.pedidos_pausados;
  return (
    <div
      className={`rounded-2xl border flex items-center gap-3 ${grande ? "p-4 md:p-5" : "px-3.5 py-2.5"} ${
        pausado ? "bg-alerta/15 border-alerta/60" : "bg-negro border-gris"
      }`}
    >
      <div className="flex-1 min-w-0">
        <b className={`block font-semibold ${grande ? "text-lg" : "text-sm"} ${pausado ? "text-alerta" : ""}`}>
          {!datos ? "Pausar pedidos" : pausado ? "Pedidos en pausa" : "Pausar pedidos"}
        </b>
        <small className="block text-tenue text-[12.5px] leading-snug">
          {error
            ? error
            : !datos
              ? "Cargando..."
              : pausado
                ? `La tienda no toma pedidos nuevos. El cliente ve: “${datos.mensaje_pausado}”`
                : "Si la cocina está desbordada, frená los pedidos nuevos un rato."}
        </small>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={!!pausado}
        aria-label="Pausar pedidos"
        disabled={!datos || ocupado}
        onClick={cambiar}
        className={`relative flex-none rounded-full transition-colors disabled:opacity-50 ${grande ? "w-[72px] h-10" : "w-14 h-8"} ${
          pausado ? "bg-alerta" : "bg-linea"
        }`}
      >
        <span
          className={`absolute top-1 rounded-full bg-white transition-all ${grande ? "w-8 h-8" : "w-6 h-6"} ${
            pausado ? (grande ? "left-9" : "left-7") : "left-1"
          }`}
        />
      </button>
    </div>
  );
}
