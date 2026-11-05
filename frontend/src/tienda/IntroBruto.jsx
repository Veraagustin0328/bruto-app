import { useCallback, useEffect, useRef, useState } from "react";
import llama from "../assets/llama.png";
import palabra from "../assets/bruto-blanco.png";
import "./intro.css";

// La animación del paletazo (docs/intro-bruto.html): pelota, paletazo, llama,
// BRUTO y Food & Grill. Sale una vez por visita y se saltea con un toque

const DURA_MS = 3700; // la secuencia termina a los ~3 s, dejo un ratito el logo
const DURA_QUIETA_MS = 1400; // con "menos movimiento" solo se ve el logo
const FADE_MS = 450;

// Agujeros de la pala: grilla dentro de la elipse, como las palas de verdad
const AGUJEROS = [];
for (let fila = 0, y = 22; y <= 118; y += 12, fila++) {
  for (let x = 18 + (fila % 2) * 6; x <= 102; x += 12) {
    const dx = (x - 60) / 44;
    const dy = (y - 76) / 58;
    if (dx * dx + dy * dy > 1) continue;
    if (y > 104 && y < 122) continue; // no tapar la franja
    AGUJEROS.push([x, y]);
  }
}

// Chispas que salen de la llama
const CHISPAS = Array.from({ length: 14 }, (_, i) => {
  const ang = (i / 14) * Math.PI * 2;
  const dist = 70 + (i % 3) * 30;
  return {
    "--x": `${Math.cos(ang) * dist}px`,
    "--y": `${Math.sin(ang) * dist * 0.8}px`,
    animationDelay: `calc(${1.45 + (i % 4) * 0.03}s * var(--k))`,
  };
});

function Pala() {
  return (
    <svg viewBox="0 0 120 250" aria-hidden="true">
      <defs>
        <linearGradient id="intro-cara-pala" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2a2522" />
          <stop offset="1" stopColor="#121010" />
        </linearGradient>
      </defs>
      {/* corazón, el triángulo que une cabeza y mango */}
      <path d="M38 140 L60 182 L82 140" fill="none" stroke="#F05C2B" strokeWidth="7" strokeLinejoin="round" />
      <ellipse cx="60" cy="76" rx="54" ry="70" fill="url(#intro-cara-pala)" stroke="#F05C2B" strokeWidth="6" />
      <g>
        {AGUJEROS.map(([x, y]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="2.6" fill="#050404" />
        ))}
      </g>
      <path d="M16 112 Q60 132 104 112" fill="none" stroke="#F05C2B" strokeWidth="3" opacity="0.8" />
      <rect x="49" y="176" width="22" height="70" rx="7" fill="#1d1a18" stroke="#3a332e" strokeWidth="2" />
      <g stroke="#F05C2B" strokeWidth="2" opacity="0.55">
        <line x1="50" y1="190" x2="70" y2="184" />
        <line x1="50" y1="202" x2="70" y2="196" />
        <line x1="50" y1="214" x2="70" y2="208" />
        <line x1="50" y1="226" x2="70" y2="220" />
      </g>
      <rect x="47" y="238" width="26" height="9" rx="4" fill="#F05C2B" />
    </svg>
  );
}

// Escala la escena de 280 x 600 para que entre entera en la pantalla
function escalaPara() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  return Math.min(w / 280, h / 600, 1.6);
}

export default function IntroBruto({ donde, onTerminar }) {
  const quieta = useRef(
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  ).current;
  const [escala, setEscala] = useState(escalaPara);
  const [saliendo, setSaliendo] = useState(false);
  const terminado = useRef(false);

  const salir = useCallback(() => {
    if (terminado.current) return;
    terminado.current = true;
    setSaliendo(true);
    setTimeout(onTerminar, FADE_MS);
  }, [onTerminar]);

  useEffect(() => {
    const t = setTimeout(salir, quieta ? DURA_QUIETA_MS : DURA_MS);
    const alCambiar = () => setEscala(escalaPara());
    window.addEventListener("resize", alCambiar);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", alCambiar);
    };
  }, [salir, quieta]);

  return (
    <div
      className={`intro${quieta ? " quieta" : ""}${saliendo ? " chau" : ""}`}
      onClick={salir}
      role="button"
      tabIndex={0}
      aria-label="Bienvenido a BRUTO. Tocá para ver la carta"
      onKeyDown={(e) => (e.key === "Enter" || e.key === " " || e.key === "Escape") && salir()}
    >
      <div className="escena" style={{ "--escala": escala }}>
        <div className="dentro">
          <div className="cancha" aria-hidden="true">
            <i className="vidrio" />
            <i className="red" />
            <i className="serv" />
            <i className="centro" />
          </div>
          <span className="saltear">Tocá para saltear</span>

          <div className="logo">
            <img className="llama" src={llama} alt="" />
            <img className="palabra" src={palabra} alt="BRUTO" />
            <span className="bajada">FOOD &amp; GRILL</span>
          </div>

          <div aria-hidden="true">
            {CHISPAS.map((estilo, i) => (
              <span key={i} className="chispa" style={estilo} />
            ))}
          </div>
          <span className="destello" aria-hidden="true" />
          <span className="estela" aria-hidden="true" />
          <span className="estela e2" aria-hidden="true" />
          <span className="estela e3" aria-hidden="true" />

          <div className="pala">
            <Pala />
          </div>
          <span className="pelota" aria-hidden="true" />

          <div className="final">
            <p>
              {donde ? (
                <>
                  Estás en <b>{donde}</b>. Pedí y <b>te lo llevamos</b>
                </>
              ) : (
                <>
                  Pedí desde la cancha y <b>te lo llevamos</b>
                </>
              )}
            </p>
            <span className="boton">VER LA CARTA</span>
          </div>
        </div>
      </div>
    </div>
  );
}
