import { useRef } from "react";
import { EVENTO_SIN_SESION, auth, borrarSesion, ws } from "../api";
import useSocket from "../lib/useSocket";

// El WebSocket del panel para las pantallas que no son de pedidos (carta,
// configuración): escucha avisos como "carta_actualizada" o "config_actualizada".
// onEvento recibe el mensaje entero; onReconecta, para traer todo de nuevo
export default function useEventosPanel(token, { onEvento, onReconecta } = {}) {
  const cb = useRef({ onEvento, onReconecta });
  cb.current = { onEvento, onReconecta };
  return useSocket(token ? ws.panel(token) : null, {
    onMensaje: (m) => m?.evento && cb.current.onEvento?.(m),
    onReconecta: () => cb.current.onReconecta?.(),
    // No pudo conectar: capaz venció el token. /yo da 401 y el api.js lleva al login
    onFallo: () => auth.yo().catch(() => {}),
    onRechazo: () => {
      borrarSesion();
      window.dispatchEvent(new Event(EVENTO_SIN_SESION));
    },
  });
}
