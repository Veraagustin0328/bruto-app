import { useEffect, useMemo, useState } from "react";
import { carta as api } from "../../api";
import { claseInput } from "../../componentes/Controles";
import { precio } from "../../lib/formato";
import { Boton } from "../comunes";

// Aumento de precios (parte 4 de la maqueta): a qué aplica, cuánto y cómo
// redondea. Muestra cómo quedan los precios ANTES de aplicar. El cálculo lo
// hace el backend (vista previa y aplicar usan la misma cuenta)

const REDONDEOS = [100, 500, 1000];

function Viejo({ children }) {
  return <td className="px-2 py-2 text-right text-tenue line-through num whitespace-nowrap">{children}</td>;
}
function Nuevo({ children }) {
  return (
    <td className="px-2 py-2 text-right font-bold num whitespace-nowrap">
      <span className="text-naranja font-normal">→ </span>
      {children}
    </td>
  );
}

export default function Aumento({ categorias, version, onAplicado, avisar }) {
  const [aplicaA, setAplicaA] = useState(() => (categorias[0] ? `cat:${categorias[0].id}` : "todo"));
  const [elegidos, setElegidos] = useState(() => new Set());
  const [porcentaje, setPorcentaje] = useState("10");
  const [redondeo, setRedondeo] = useState(500);
  const [previa, setPrevia] = useState(null);
  const [error, setError] = useState(null);
  const [calculando, setCalculando] = useState(false);
  const [aplicando, setAplicando] = useState(false);

  // Para saber si una opción es de "elegís una" (Simple/Doble) o un agregado
  const tipoDeOpcion = useMemo(() => {
    const m = new Map();
    for (const c of categorias) for (const p of c.productos) for (const g of p.grupos) for (const o of g.opciones) m.set(o.id, g.tipo);
    return m;
  }, [categorias]);

  const pct = Number(String(porcentaje).replace(",", "."));
  const datos = useMemo(() => {
    if (!porcentaje.trim() || !Number.isFinite(pct) || pct === 0 || pct <= -50 || pct > 200) return null;
    if (aplicaA === "todo") return { aplica_a: "todo", porcentaje: pct, redondeo };
    if (aplicaA === "productos") return elegidos.size ? { aplica_a: "productos", producto_ids: [...elegidos], porcentaje: pct, redondeo } : null;
    return { aplica_a: "categoria", categoria_id: Number(aplicaA.slice(4)), porcentaje: pct, redondeo };
  }, [aplicaA, elegidos, pct, porcentaje, redondeo]);

  // Vista previa: se pide sola cuando cambia algo (y si cambió la carta)
  const clave = JSON.stringify(datos);
  useEffect(() => {
    if (!datos) {
      setPrevia(null);
      return undefined;
    }
    let vivo = true;
    setCalculando(true);
    const t = setTimeout(() => {
      api
        .vistaPrevia(datos)
        .then((r) => {
          if (!vivo) return;
          setPrevia(r);
          setError(null);
        })
        .catch((e) => vivo && setError(e.message))
        .finally(() => vivo && setCalculando(false));
    }, 350);
    return () => {
      vivo = false;
      clearTimeout(t);
    };
  }, [clave, version]); // eslint-disable-line react-hooks/exhaustive-deps

  async function aplicar() {
    if (!datos || !previa) return;
    setAplicando(true);
    setError(null);
    try {
      const r = await api.aplicarAumento(datos);
      avisar(`Listo: se actualizaron ${r.cantidad_precios} precios`);
      setPorcentaje("");
      setPrevia(null);
      onAplicado?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setAplicando(false);
    }
  }

  // Los agregados (ej. Extra carne y queso) se repiten en cada burger: una fila sola
  const filasAgregados = useMemo(() => {
    if (!previa) return [];
    const m = new Map();
    for (const p of previa.productos) {
      for (const o of p.opciones) {
        if (tipoDeOpcion.get(o.opcion_id) === "unica") continue;
        const k = `${o.nombre}|${o.extra_viejo}|${o.extra_nuevo}`;
        const fila = m.get(k) || { ...o, veces: 0 };
        fila.veces += 1;
        m.set(k, fila);
      }
    }
    return [...m.values()];
  }, [previa, tipoDeOpcion]);

  const hayDoble = previa?.productos.some((p) => p.opciones.some((o) => tipoDeOpcion.get(o.opcion_id) === "unica"));

  function tocarProducto(id) {
    setElegidos((s) => {
      const sig = new Set(s);
      if (sig.has(id)) sig.delete(id);
      else sig.add(id);
      return sig;
    });
  }

  return (
    <section className="grid gap-4 bg-negro border border-gris rounded-2xl p-4 md:p-5">
      <div>
        <h2 className="text-[28px]">Aumento de precios</h2>
        <p className="text-tenue text-[13px]">Revisá cómo quedan antes de aplicar. Los pedidos que ya se hicieron no cambian.</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-[1.4fr_0.8fr_1fr] gap-3">
        <label className="grid gap-1 col-span-2 sm:col-span-1">
          <span className="text-xs text-tenue font-medium">Aplicar a</span>
          <select className={claseInput} value={aplicaA} onChange={(e) => setAplicaA(e.target.value)}>
            <option value="todo">Toda la carta</option>
            {categorias.map((c) => (
              <option key={c.id} value={`cat:${c.id}`}>
                {c.nombre}
              </option>
            ))}
            <option value="productos">Productos sueltos...</option>
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-xs text-tenue font-medium">Subir</span>
          <span className="relative">
            <input
              className={`${claseInput} pr-8 num`}
              inputMode="decimal"
              value={porcentaje}
              onChange={(e) => setPorcentaje(e.target.value.replace(/[^\d,.-]/g, ""))}
              aria-describedby="ayuda-pct"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-tenue">%</span>
          </span>
        </label>
        <label className="grid gap-1">
          <span className="text-xs text-tenue font-medium">Redondear a</span>
          <select className={`${claseInput} num`} value={redondeo} onChange={(e) => setRedondeo(Number(e.target.value))}>
            {REDONDEOS.map((r) => (
              <option key={r} value={r}>
                {precio(r)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p id="ayuda-pct" className="text-tenue text-xs -mt-2">
        Para bajar, poné un número negativo (ej: -10). Redondea al más cercano: $13.750 queda $14.000.
      </p>

      {aplicaA === "productos" && (
        <div className="max-h-56 overflow-y-auto rounded-xl border border-gris p-2 grid gap-2">
          {categorias.map((c) => (
            <fieldset key={c.id} className="grid gap-1">
              <legend className="text-[11px] tracking-[0.15em] uppercase text-tenue font-semibold px-1">{c.nombre}</legend>
              {c.productos.map((p) => (
                <label key={p.id} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg hover:bg-carbon text-sm">
                  <span className="flex items-center gap-2">
                    <input type="checkbox" className="accent-[#f05c2b] w-4 h-4" checked={elegidos.has(p.id)} onChange={() => tocarProducto(p.id)} />
                    {p.nombre}
                  </span>
                  <span className="num text-tenue">{precio(p.precio)}</span>
                </label>
              ))}
            </fieldset>
          ))}
        </div>
      )}

      {error && <p className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm">{error}</p>}

      {!datos ? (
        <p className="text-tenue text-sm border border-dashed border-gris rounded-xl p-4 text-center">
          {aplicaA === "productos" && !elegidos.size ? "Elegí los productos." : "Poné un porcentaje para ver cómo quedan los precios."}
        </p>
      ) : !previa ? (
        <div className="h-40 rounded-xl bg-carbon animate-pulse" aria-label="Calculando" />
      ) : (
        <div className={`overflow-x-auto -mx-1 transition-opacity ${calculando ? "opacity-60" : ""}`}>
          <table className="w-full text-[13.5px] border-collapse">
            <thead>
              <tr className="text-tenue text-[11.5px] border-b border-linea">
                <th className="text-left font-medium px-2 py-1.5">Producto</th>
                <th className="text-right font-medium px-2 py-1.5" colSpan={2}>
                  Precio
                </th>
                {hayDoble && (
                  <th className="text-right font-medium px-2 py-1.5" colSpan={2}>
                    Doble
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {previa.productos.map((p) => {
                const unicas = p.opciones.filter((o) => tipoDeOpcion.get(o.opcion_id) === "unica");
                return (
                  <tr key={p.producto_id} className="border-b border-gris align-top">
                    <td className="px-2 py-2">{p.nombre}</td>
                    <Viejo>{precio(p.precio_viejo)}</Viejo>
                    <Nuevo>{precio(p.precio_nuevo)}</Nuevo>
                    {hayDoble &&
                      (unicas.length ? (
                        <>
                          <Viejo>
                            {unicas.map((o) => (
                              <span key={o.opcion_id} className="block">
                                {o.nombre !== "Doble" && <small className="no-underline mr-1">{o.nombre}</small>}
                                {precio(o.final_viejo)}
                              </span>
                            ))}
                          </Viejo>
                          <Nuevo>
                            {unicas.map((o, i) => (
                              <span key={o.opcion_id} className={i ? "block" : ""}>
                                {precio(o.final_nuevo)}
                              </span>
                            ))}
                          </Nuevo>
                        </>
                      ) : (
                        <td colSpan={2} className="px-2 py-2 text-right text-tenue">
                          no tiene
                        </td>
                      ))}
                  </tr>
                );
              })}
              {filasAgregados.map((o) => (
                <tr key={`${o.nombre}-${o.extra_viejo}`} className="border-b border-gris">
                  <td className="px-2 py-2">
                    {o.nombre}
                    {o.veces > 1 && <small className="text-tenue"> · en {o.veces} productos</small>}
                  </td>
                  <Viejo>{precio(o.extra_viejo)}</Viejo>
                  <Nuevo>{precio(o.extra_nuevo)}</Nuevo>
                  {hayDoble && <td colSpan={2} />}
                </tr>
              ))}
            </tbody>
          </table>
          {previa.productos.length === 0 && <p className="text-tenue text-sm p-3">No hay productos para aumentar.</p>}
        </div>
      )}

      <div className="flex justify-end gap-2.5 flex-wrap">
        <Boton
          secundario
          grande
          disabled={aplicando}
          onClick={() => {
            setPorcentaje("");
            setElegidos(new Set());
            setError(null);
          }}
        >
          Cancelar
        </Boton>
        <Boton grande disabled={!previa || !datos || calculando || aplicando || previa.cantidad_precios === 0} onClick={aplicar}>
          {aplicando ? "Aplicando..." : previa ? `Aplicar a ${previa.cantidad_precios} precios` : "Aplicar"}
        </Boton>
      </div>
    </section>
  );
}
