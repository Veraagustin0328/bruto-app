import { useCallback, useEffect, useRef, useState } from "react";

// El "ding" de pedido nuevo, hecho con Web Audio (sin archivos de sonido).
// Los navegadores no dejan sonar nada hasta que el usuario toca la página,
// así que se habilita con el primer toque o tecla
export default function useSonido() {
  const ctx = useRef(null);
  const [habilitado, setHabilitado] = useState(false);

  useEffect(() => {
    function habilitar() {
      try {
        if (!ctx.current) {
          const Ctx = window.AudioContext || window.webkitAudioContext;
          if (!Ctx) return;
          ctx.current = new Ctx();
        }
        ctx.current.resume?.();
        // La barra de "activar el sonido" se va recién cuando termina el toque:
        // si se fuera en el pointerdown, todo se corre para arriba antes del
        // click y el primer botón que tocan no anda
        setTimeout(() => setHabilitado(true), 350);
      } catch {
        // sin audio: seguimos sin sonido
      }
    }
    window.addEventListener("pointerdown", habilitar);
    window.addEventListener("keydown", habilitar);
    return () => {
      window.removeEventListener("pointerdown", habilitar);
      window.removeEventListener("keydown", habilitar);
    };
  }, []);

  const sonar = useCallback(() => {
    const c = ctx.current;
    if (!c || c.state !== "running") return;
    // Dos notas cortas y fuertes, para que se escuche con la plancha prendida
    [
      [0, 880],
      [0.18, 1320],
      [0.5, 880],
      [0.68, 1320],
    ].forEach(([cuando, frecuencia]) => {
      const osc = c.createOscillator();
      const vol = c.createGain();
      osc.type = "square";
      osc.frequency.value = frecuencia;
      const t = c.currentTime + cuando;
      vol.gain.setValueAtTime(0.0001, t);
      vol.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
      vol.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
      osc.connect(vol).connect(c.destination);
      osc.start(t);
      osc.stop(t + 0.18);
    });
  }, []);

  return { sonar, habilitado };
}
