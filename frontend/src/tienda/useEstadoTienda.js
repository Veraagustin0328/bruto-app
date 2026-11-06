import { useCallback, useEffect, useState } from "react";
import { tienda } from "../api";

// Abierta, cerrada o pausada, en vivo: pregunta cada 20 s y al volver a la
// pestaña. Así si la cantina pausa los pedidos o se pasa la hora de cierre,
// el cliente lo ve sin recargar. Si falla, se queda con lo último que supo
const CADA_MS = 20000;

export default function useEstadoTienda() {
  const [estado, setEstado] = useState(null);
  const [fallo, setFallo] = useState(false);

  const consultar = useCallback(() => {
    tienda
      .estado()
      .then((e) => {
        setEstado(e);
        setFallo(false);
      })
      .catch(() => setFallo(true));
  }, []);

  useEffect(() => {
    consultar();
    const t = setInterval(consultar, CADA_MS);
    const alVolver = () => document.visibilityState === "visible" && consultar();
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [consultar]);

  return { estado, fallo, consultar };
}
