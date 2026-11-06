import { useEffect, useRef, useState } from "react";

// WebSocket que se mantiene vivo solo:
// - manda "ping" cada 25 s (el backend contesta "pong")
// - si se corta, reconecta esperando 1, 2, 4... hasta 15 s
// - si el backend lo cierra por permiso (código 1008), no insiste y avisa con onRechazo
//
// url: null para no conectar. onMensaje recibe el JSON ya parseado.
// onReconecta se llama cada vez que vuelve a conectar después de un corte,
// para traer de nuevo lo que se pudo haber perdido mientras tanto.
// onFallo se llama cuando un intento se cae sin llegar a conectar. Ojo: si el
// backend rechaza el token antes de aceptar, el navegador ve un corte común
// (1006, no 1008), así que el panel usa esto para chequear si venció la sesión
export default function useSocket(url, { onMensaje, onRechazo, onReconecta, onFallo } = {}) {
  const [conectado, setConectado] = useState(false);
  const callbacks = useRef({ onMensaje, onRechazo, onReconecta, onFallo });
  callbacks.current = { onMensaje, onRechazo, onReconecta, onFallo };

  useEffect(() => {
    if (!url) return undefined;

    let socket = null;
    let ping = null;
    let reintento = null;
    let espera = 1000;
    let cortado = false; // ya se había conectado alguna vez y se cayó
    let terminado = false;

    function conectar() {
      socket = new WebSocket(url);
      let abrio = false;

      socket.onopen = () => {
        abrio = true;
        setConectado(true);
        espera = 1000;
        if (cortado) callbacks.current.onReconecta?.();
        ping = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send("ping");
        }, 25000);
      };

      socket.onmessage = (e) => {
        if (e.data === "pong") return;
        try {
          callbacks.current.onMensaje?.(JSON.parse(e.data));
        } catch {
          // mensaje raro: lo ignoro
        }
      };

      socket.onclose = (e) => {
        clearInterval(ping);
        setConectado(false);
        if (terminado) return;
        if (e.code === 1008) {
          callbacks.current.onRechazo?.();
          return;
        }
        cortado = true;
        if (!abrio) callbacks.current.onFallo?.();
        reintento = setTimeout(conectar, espera);
        espera = Math.min(espera * 2, 15000);
      };
    }

    conectar();

    // Al volver a la pestaña (o prender la pantalla del celu) reconecto al toque
    function alVolver() {
      if (document.visibilityState === "visible" && socket?.readyState === WebSocket.CLOSED && !terminado) {
        clearTimeout(reintento);
        espera = 1000;
        conectar();
      }
    }
    document.addEventListener("visibilitychange", alVolver);

    return () => {
      terminado = true;
      clearInterval(ping);
      clearTimeout(reintento);
      document.removeEventListener("visibilitychange", alVolver);
      socket?.close();
    };
  }, [url]);

  return conectado;
}
