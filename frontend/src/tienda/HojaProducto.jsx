import { useEffect, useMemo, useState } from "react";
import { Campo, Radio, Stepper, claseInput } from "../componentes/Controles";
import { topeOpcion, usaStepper } from "../lib/carta";
import { precio } from "../lib/formato";
import { Badge, FotoProducto } from "./Carta";

// La hoja que sube desde abajo para armar el producto (pantalla 2 de la maqueta)

function CabeceraGrupo({ grupo }) {
  let etiqueta = grupo.obligatorio ? "Obligatorio" : "Opcional";
  if (grupo.tipo === "multiple" && grupo.max_selecciones) etiqueta += ` · hasta ${grupo.max_selecciones}`;
  return (
    <div className="flex justify-between items-center font-semibold text-sm">
      {grupo.nombre}
      <small
        className={`font-medium text-[11px] px-2 py-0.5 rounded ${
          grupo.obligatorio ? "bg-naranja/15 text-naranja" : "bg-gris text-tenue"
        }`}
      >
        {etiqueta}
      </small>
    </div>
  );
}

function Opcion({ opcion, grupo, cantidad, producto, lleno, onCambiar }) {
  const on = cantidad > 0;
  const base =
    "w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl bg-carbon border text-sm text-left";

  if (!opcion.disponible) {
    return (
      <div className={`${base} border-gris opacity-45`}>
        <span>{opcion.nombre}</span>
        <span className="text-tenue text-xs">Hoy no hay</span>
      </div>
    );
  }

  // En "Tamaño" muestro el precio final (Simple $13.500 / Doble $15.000), como la maqueta
  const extra = Number(opcion.precio_extra);
  const textoPrecio =
    grupo.tipo === "unica" && grupo.obligatorio
      ? precio(Number(producto.precio) + extra)
      : extra > 0
        ? `+${precio(extra)}`
        : "";

  if (grupo.tipo === "multiple" && usaStepper(opcion)) {
    const tope = topeOpcion(opcion);
    return (
      <div className={`${base} ${on ? "border-naranja" : "border-gris"}`}>
        <span className="flex flex-wrap items-baseline gap-x-2">
          {opcion.nombre}
          {textoPrecio && <span className="num text-tenue text-xs">{textoPrecio}</span>}
        </span>
        <Stepper
          valor={cantidad}
          etiqueta={opcion.nombre}
          puedeMenos={cantidad > 0}
          puedeMas={cantidad < tope && (on || !lleno)}
          onMenos={() => onCambiar(cantidad - 1)}
          onMas={() => onCambiar(cantidad + 1)}
        />
      </div>
    );
  }

  // Radio (única) o tilde (múltiple de a uno)
  const bloqueada = !on && grupo.tipo === "multiple" && lleno;
  return (
    <button
      type="button"
      role={grupo.tipo === "unica" ? "radio" : "checkbox"}
      aria-checked={on}
      disabled={bloqueada}
      onClick={() => onCambiar(on ? 0 : 1)}
      className={`${base} ${on ? "border-naranja" : "border-gris"} disabled:opacity-45`}
    >
      <span className="flex items-center gap-2.5">
        <Radio on={on} cuadrado={grupo.tipo === "multiple"} />
        {opcion.nombre}
      </span>
      {textoPrecio && <span className="num text-tenue text-xs">{textoPrecio}</span>}
    </button>
  );
}

export default function HojaProducto({ producto, onCerrar, onAgregar }) {
  // { [opcion_id]: cantidad }
  const [elegidas, setElegidas] = useState({});
  const [nota, setNota] = useState("");
  const [cantidad, setCantidad] = useState(1);

  // Mientras está abierta, la carta de atrás no scrollea. Escape la cierra
  useEffect(() => {
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const alTeclear = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", alTeclear);
    return () => {
      document.body.style.overflow = antes;
      window.removeEventListener("keydown", alTeclear);
    };
  }, [onCerrar]);

  function cambiar(grupo, opcion, nueva) {
    setElegidas((actual) => {
      const sig = { ...actual };
      // En los de opción única, elegir una apaga las otras del grupo
      if (grupo.tipo === "unica") grupo.opciones.forEach((o) => delete sig[o.id]);
      if (nueva > 0) sig[opcion.id] = nueva;
      else delete sig[opcion.id];
      return sig;
    });
  }

  const { unitario, faltan } = useMemo(() => {
    let unitario = Number(producto.precio);
    const faltan = [];
    for (const g of producto.grupos) {
      let alguna = false;
      for (const o of g.opciones) {
        const c = elegidas[o.id] || 0;
        if (c > 0) {
          alguna = true;
          unitario += Number(o.precio_extra) * c;
        }
      }
      if (g.obligatorio && !alguna) faltan.push(g.nombre.toLowerCase());
    }
    return { unitario, faltan };
  }, [producto, elegidas]);

  function agregar() {
    if (faltan.length) return;
    const opciones = [];
    for (const g of producto.grupos) {
      for (const o of g.opciones) {
        const c = elegidas[o.id] || 0;
        if (c > 0) {
          opciones.push({
            opcion_id: o.id,
            cantidad: c,
            nombre: o.nombre,
            grupo: g.nombre,
            precio_extra: Number(o.precio_extra),
          });
        }
      }
    }
    onAgregar({
      producto_id: producto.id,
      nombre: producto.nombre,
      precio_unitario: unitario,
      cantidad,
      nota: nota.trim() || null,
      opciones,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" role="dialog" aria-modal="true" aria-label={producto.nombre}>
      <button
        type="button"
        aria-label="Cerrar"
        onClick={onCerrar}
        className="absolute inset-0 bg-black/70 animate-[aparecer_.2s_ease-out]"
      />
      <div className="relative w-full max-w-[560px] max-h-[92dvh] flex flex-col bg-negro rounded-t-3xl overflow-hidden animate-[subir_.25s_ease-out]">
        <div className="relative h-36 flex-none">
          <FotoProducto producto={producto} className="w-full h-full" />
          <button
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar"
            className="absolute top-3 left-3 w-9 h-9 rounded-full bg-black/60 grid place-items-center text-lg"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto overscroll-contain px-4 pt-3 pb-4 flex flex-col gap-4">
          <div>
            <h3 className="text-[34px] flex flex-wrap items-center gap-2">
              {producto.nombre}
              {producto.etiqueta && <Badge>{producto.etiqueta}</Badge>}
            </h3>
            {producto.descripcion && <p className="text-tenue text-[13px] leading-snug mt-1">{producto.descripcion}</p>}
          </div>

          {producto.grupos.map((g) => {
            const cuantas = g.opciones.filter((o) => elegidas[o.id] > 0).length;
            const lleno = g.max_selecciones !== null && cuantas >= g.max_selecciones;
            return (
              <div key={g.id} className="grid gap-2" role={g.tipo === "unica" ? "radiogroup" : "group"} aria-label={g.nombre}>
                <CabeceraGrupo grupo={g} />
                {g.opciones.map((o) => (
                  <Opcion
                    key={o.id}
                    opcion={o}
                    grupo={g}
                    producto={producto}
                    cantidad={elegidas[o.id] || 0}
                    lleno={lleno}
                    onCambiar={(n) => cambiar(g, o, n)}
                  />
                ))}
              </div>
            );
          })}

          <Campo etiqueta="¿Algo para la cocina?" id="nota-item">
            <input
              id="nota-item"
              className={claseInput}
              placeholder="Ej: sin pepinillos"
              maxLength={200}
              value={nota}
              onChange={(e) => setNota(e.target.value)}
            />
          </Campo>
        </div>

        <div className="flex-none flex items-center gap-3 px-3 pt-2 pb-[max(14px,env(safe-area-inset-bottom))] border-t border-gris">
          <Stepper
            valor={cantidad}
            etiqueta={producto.nombre}
            puedeMenos={cantidad > 1}
            puedeMas={cantidad < 20}
            onMenos={() => setCantidad((c) => c - 1)}
            onMas={() => setCantidad((c) => c + 1)}
          />
          <button
            type="button"
            onClick={agregar}
            disabled={faltan.length > 0}
            className="flex-1 rounded-2xl py-3.5 font-bold tracking-wide text-sm bg-naranja text-white disabled:bg-gris disabled:text-tenue num"
          >
            {faltan.length ? `ELEGÍ ${faltan[0].toUpperCase()}` : `AGREGAR · ${precio(unitario * cantidad)}`}
          </button>
        </div>
      </div>
    </div>
  );
}
