import { useEffect, useRef, useState } from "react";
import llama from "../assets/llama.png";
import { precioDoble } from "../lib/carta";
import { precio } from "../lib/formato";

// Mientras no haya fotos en el backend: fondo oscuro con la llama
export function FotoProducto({ producto, className = "" }) {
  if (producto.imagen_url) {
    return (
      <img
        src={producto.imagen_url}
        alt={producto.nombre}
        loading="lazy"
        className={`object-cover bg-carbon ${className}`}
      />
    );
  }
  return (
    <div className={`grid place-items-center bg-gradient-to-br from-gris to-negro ${className}`}>
      <img src={llama} alt="" className="w-[38%] max-w-16 opacity-30" />
    </div>
  );
}

export function Badge({ children, apagado = false }) {
  return (
    <span
      className={`font-sans text-[10px] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded leading-none ${
        apagado ? "bg-gris text-tenue" : "bg-naranja text-white"
      }`}
    >
      {children}
    </span>
  );
}

function ProductoCard({ producto, onElegir }) {
  const doble = precioDoble(producto);
  const apagado = !producto.disponible;

  return (
    <button
      type="button"
      disabled={apagado}
      onClick={() => onElegir?.(producto)}
      aria-label={apagado ? `${producto.nombre}, no disponible` : undefined}
      className={`w-full text-left grid grid-cols-[84px_1fr] gap-3 p-2 rounded-2xl bg-carbon border border-gris items-center transition ${
        apagado ? "opacity-45 cursor-not-allowed" : "active:scale-[0.99] hover:border-linea"
      }`}
    >
      <FotoProducto producto={producto} className="w-[84px] h-[84px] rounded-xl" />
      <div className="min-w-0 pr-1">
        <h4 className="font-display text-[22px] leading-none tracking-wide flex flex-wrap items-center gap-1.5">
          {producto.nombre}
          {producto.etiqueta && <Badge apagado={apagado}>{producto.etiqueta}</Badge>}
          {apagado && !producto.etiqueta && <Badge apagado>Hoy no hay</Badge>}
        </h4>
        {producto.descripcion && (
          <p className="text-tenue text-xs leading-snug line-clamp-2 mt-1 mb-1.5">
            {producto.descripcion}
          </p>
        )}
        <div className="num font-semibold text-sm mt-1">
          {precio(producto.precio)}
          {doble !== null && (
            <span className="text-tenue font-normal text-xs"> · doble {precio(doble)}</span>
          )}
        </div>
      </div>
    </button>
  );
}

// Chips de categorías: al tocar uno, scroll a esa categoría.
// Mientras scrolleás, se prende el de la categoría que estás viendo
function Chips({ categorias, activa, onTocar }) {
  const contenedor = useRef(null);

  // Que el chip prendido quede a la vista en la fila
  useEffect(() => {
    const chip = contenedor.current?.querySelector(`[data-cat="${activa}"]`);
    chip?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [activa]);

  return (
    <nav
      ref={contenedor}
      aria-label="Categorías"
      className="flex gap-2 overflow-x-auto sin-scrollbar px-4 py-2"
    >
      {categorias.map((c) => (
        <button
          key={c.id}
          type="button"
          data-cat={c.id}
          onClick={() => onTocar(c.id)}
          className={`flex-none px-3.5 py-1.5 rounded-full border text-[13px] whitespace-nowrap transition ${
            activa === c.id
              ? "bg-naranja border-naranja text-white font-semibold"
              : "border-linea text-tenue"
          }`}
        >
          {c.nombre}
        </button>
      ))}
    </nav>
  );
}

export function Carta({ categorias, onElegir, arriba, avisos }) {
  const [activa, setActiva] = useState(categorias[0]?.id);
  const tocando = useRef(false);

  // Cuál categoría se está viendo: la última cuyo título pasó la barra de arriba
  useEffect(() => {
    function alScrollear() {
      if (tocando.current) return;
      let actual = categorias[0]?.id;
      for (const c of categorias) {
        const el = document.getElementById(`cat-${c.id}`);
        if (el && el.getBoundingClientRect().top < 90) actual = c.id;
      }
      setActiva(actual);
    }
    window.addEventListener("scroll", alScrollear, { passive: true });
    return () => window.removeEventListener("scroll", alScrollear);
  }, [categorias]);

  function irA(id) {
    setActiva(id);
    // Mientras dura el scroll suave no dejo que el scroll cambie el chip
    tocando.current = true;
    document.getElementById(`cat-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => (tocando.current = false), 700);
  }

  return (
    <>
      {arriba}
      {avisos}
      {/* Los chips quedan pegados arriba mientras scrolleás */}
      <div className="sticky top-0 z-20 bg-negro/95 backdrop-blur">
        <Chips categorias={categorias} activa={activa} onTocar={irA} />
      </div>
      <div className="px-4 pb-32 flex flex-col gap-6 mt-2">
        {categorias.map((c) => (
          <section key={c.id} id={`cat-${c.id}`} className="scroll-mt-16 flex flex-col gap-2.5">
            <h3 className="text-[26px]">{c.nombre}</h3>
            {c.productos.map((p) => (
              <ProductoCard key={p.id} producto={p} onElegir={onElegir} />
            ))}
          </section>
        ))}
        <p className="text-center text-tenue text-xs mt-2">
          BRUTO · Food &amp; Grill · Los precios pueden cambiar sin aviso
        </p>
      </div>
    </>
  );
}

// Lo que se ve mientras llega la carta
export function EsqueletoCarta() {
  return (
    <div className="px-4 flex flex-col gap-3 animate-pulse" aria-label="Cargando la carta">
      <div className="flex gap-2 py-2">
        {[110, 90, 70, 96].map((w, i) => (
          <div key={i} className="h-8 rounded-full bg-gris" style={{ width: w }} />
        ))}
      </div>
      <div className="h-7 w-44 rounded bg-gris mt-1" />
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="grid grid-cols-[84px_1fr] gap-3 p-2 rounded-2xl bg-carbon border border-gris">
          <div className="w-[84px] h-[84px] rounded-xl bg-gris" />
          <div className="flex flex-col gap-2 justify-center">
            <div className="h-5 w-2/3 rounded bg-gris" />
            <div className="h-3 w-full rounded bg-gris" />
            <div className="h-3 w-4/5 rounded bg-gris" />
            <div className="h-4 w-1/3 rounded bg-gris" />
          </div>
        </div>
      ))}
    </div>
  );
}
