import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EVENTO_SIN_SESION, auth, borrarSesion, panel, ws } from "../api";
import useSocket from "../lib/useSocket";

// Lista de pedidos de la jornada que se mantiene sola por WebSocket.
// La usan el panel de la cantina y la cocina, cada uno con sus estados
//
// estados: los que se muestran (el resto se saca de la lista)
// onNuevo: se llama cuando entra un pedido nuevo (para el sonido)
// onEvento: los otros avisos del WebSocket (ej. config_actualizada)

const BRILLA_MS = 8000; // cuánto brilla la tarjeta de un pedido recién entrado
const RECARGA_MS = 2 * 60 * 1000; // por las dudas, cada tanto traigo todo de nuevo

export default function usePedidosEnVivo(token, estados, { onNuevo, onEvento } = {}) {
  const [porId, setPorId] = useState(() => new Map());
  const [cargando, setCargando] = useState(true);
  const [recargando, setRecargando] = useState(false);
  const [error, setError] = useState(null);
  const [destacados, setDestacados] = useState(() => new Set());
  const estadosRef = useRef(estados);
  estadosRef.current = estados;
  const onNuevoRef = useRef(onNuevo);
  onNuevoRef.current = onNuevo;
  const onEventoRef = useRef(onEvento);
  onEventoRef.current = onEvento;
  // Todos los pedidos que esta pantalla ya vio alguna vez. Sirve para darse
  // cuenta de los que entraron mientras el WebSocket estaba cortado
  const vistos = useRef(new Set());
  const yaCargo = useRef(false);

  const destacar = useCallback((id) => {
    setDestacados((s) => new Set(s).add(id));
    setTimeout(() => {
      setDestacados((s) => {
        const sig = new Set(s);
        sig.delete(id);
        return sig;
      });
    }, BRILLA_MS);
  }, []);

  const recargar = useCallback(async () => {
    setRecargando(true);
    try {
      const lista = (await panel.pedidos()).filter((p) => estadosRef.current.includes(p.estado));
      // Los "recibido" que no conocíamos entraron durante un corte: suenan y
      // brillan como si llegaran recién. En la primera carga no (ya estaban)
      const perdidos = yaCargo.current
        ? lista.filter((p) => p.estado === "recibido" && !vistos.current.has(p.id))
        : [];
      lista.forEach((p) => vistos.current.add(p.id));
      yaCargo.current = true;
      setPorId(new Map(lista.map((p) => [p.id, p])));
      perdidos.forEach((p) => destacar(p.id));
      if (perdidos.length) onNuevoRef.current?.(perdidos[0]); // un solo ding aunque sean varios
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
      setRecargando(false);
    }
  }, [destacar]);

  useEffect(() => {
    recargar();
    const t = setInterval(recargar, RECARGA_MS);
    return () => clearInterval(t);
  }, [recargar]);

  // Mete o saca un pedido según su estado. Lo usan el WebSocket y las respuestas de los botones
  const actualizar = useCallback((p) => {
    vistos.current.add(p.id);
    setPorId((actual) => {
      const sig = new Map(actual);
      if (estadosRef.current.includes(p.estado)) sig.set(p.id, p);
      else sig.delete(p.id); // entregado, cancelado o pasó a otra pantalla
      return sig;
    });
  }, []);

  const conectado = useSocket(token ? ws.panel(token) : null, {
    onMensaje: (m) => {
      if (!m.pedido) {
        onEventoRef.current?.(m); // ej: config_actualizada
        return;
      }
      if (m.evento === "pedido_nuevo" && estadosRef.current.includes(m.pedido.estado) && !vistos.current.has(m.pedido.id)) {
        destacar(m.pedido.id);
        onNuevoRef.current?.(m.pedido);
      }
      actualizar(m.pedido);
    },
    // Volvió internet: traigo todo por si me perdí algo mientras tanto
    onReconecta: recargar,
    // No pudo conectar: capaz venció el token. /yo da 401 y el api.js lleva al login
    onFallo: () => auth.yo().catch(() => {}),
    // El backend no acepta el token (venció o dieron de baja al usuario)
    onRechazo: () => {
      borrarSesion();
      window.dispatchEvent(new Event(EVENTO_SIN_SESION));
    },
  });

  const lista = useMemo(() => [...porId.values()].sort((a, b) => a.numero - b.numero), [porId]);

  return { lista, cargando, recargando, error, conectado, recargar, actualizar, destacados };
}

// Un "ahora" que se actualiza solo, para los relojes de las tarjetas
export function useAhora(cadaMs = 1000) {
  const [ahora, setAhora] = useState(Date.now);
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), cadaMs);
    return () => clearInterval(t);
  }, [cadaMs]);
  return ahora;
}
