import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { caja as api } from "../api";
import { claseInput } from "../componentes/Controles";
import { precio } from "../lib/formato";
import { AvisoConexion, Avisos, Boton, EnVivo, Esqueleto, Titulo, useAvisos } from "./comunes";
import Marco from "./Marco";
import useEventosPanel from "./useEventosPanel";

// Caja del día: lo que se vendió en la jornada (de 6 a 6). La cantina ve la de
// hoy; el admin puede elegir otro día y ver el historial de los últimos 30

// "2026-11-05" → Date local (sin que el navegador lo corra por la zona horaria)
function aFecha(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

// "2026-11-05" → "Jueves 5/11"
export function nombreDia(iso, conAnio = false) {
  const f = aFecha(iso);
  const dia = f.toLocaleDateString("es-AR", { weekday: "long" });
  return `${dia.charAt(0).toUpperCase()}${dia.slice(1)} ${f.getDate()}/${f.getMonth() + 1}${conAnio ? `/${f.getFullYear()}` : ""}`;
}

// El texto para mandar por WhatsApp
export function textoResumen(c) {
  const pedidos = `${c.pedidos} ${c.pedidos === 1 ? "pedido" : "pedidos"}`;
  return `BRUTO · ${nombreDia(c.fecha)} · ${pedidos} · ${precio(c.vendido)} (MP ${precio(c.mercadopago)} / efectivo ${precio(c.efectivo_cobrado)})`;
}

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    // Sin https (la wifi del local) no hay clipboard: el truco viejo
    const area = document.createElement("textarea");
    area.value = texto;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

function Cuadro({ titulo, valor, detalle, alerta = false, grande = false }) {
  return (
    <div className={`bg-negro border rounded-xl px-3.5 py-3 ${alerta ? "border-alerta/50" : "border-gris"} ${grande ? "col-span-2" : ""}`}>
      <small className="text-tenue text-[11.5px] block">{titulo}</small>
      <b className={`block font-bold num leading-tight ${grande ? "text-[30px] md:text-[34px]" : "text-[20px] md:text-[22px]"} ${alerta ? "text-alerta" : ""}`}>{valor}</b>
      {detalle && <small className="text-tenue text-[12px] block mt-0.5">{detalle}</small>}
    </div>
  );
}

// Barras de ventas por hora, en SVG (sin librerías). Muestra desde la primera
// hora con ventas hasta la última; si no hubo nada, el horario típico
function VentasPorHora({ horas }) {
  const conVentas = horas.map((h, i) => (h.pedidos ? i : -1)).filter((i) => i >= 0);
  let desde = conVentas.length ? conVentas[0] : 12; // 18 hs
  let hasta = conVentas.length ? conVentas.at(-1) : 18; // 0 hs
  // Por lo menos 8 horas, así una sola hora con ventas no queda como una pared
  while (hasta - desde < 7) {
    if (desde > 0) desde -= 1;
    if (hasta - desde < 7 && hasta < 23) hasta += 1;
  }
  const lista = horas.slice(desde, hasta + 1);
  const max = Math.max(1, ...lista.map((h) => h.total));
  const pico = lista.reduce((a, b) => (b.total > a.total ? b : a), lista[0]);

  const ancho = 100 / lista.length;
  const ALTO = 150;
  return (
    <div className="grid gap-2">
      {conVentas.length > 0 && (
        <p className="text-tenue text-[13px]">
          Se llenó a las <b className="text-texto">{String(pico.hora).padStart(2, "0")} hs</b>: {pico.pedidos} {pico.pedidos === 1 ? "pedido" : "pedidos"} · {precio(pico.total)}
        </p>
      )}
      <svg viewBox={`0 0 100 ${ALTO + 22}`} preserveAspectRatio="none" className="w-full h-48" role="img" aria-label="Ventas por hora">
        <line x1="0" x2="100" y1={ALTO} y2={ALTO} stroke="var(--color-linea)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
        {lista.map((h, i) => {
          const alto = (h.total / max) * (ALTO - 14);
          const x = i * ancho + ancho * 0.18;
          const w = ancho * 0.64;
          return (
            <g key={h.hora}>
              <title>{`${String(h.hora).padStart(2, "0")} hs: ${h.pedidos} pedidos, ${precio(h.total)}`}</title>
              <rect x={x} y={ALTO - alto} width={w} height={Math.max(alto, h.pedidos ? 0.8 : 0)} rx="0.8" fill={h === pico && h.total ? "var(--color-naranja)" : "#8a3a20"} />
            </g>
          );
        })}
      </svg>
      {/* Las etiquetas van en HTML: en el SVG estirado la letra se deformaría */}
      <div className="grid -mt-7 text-[10.5px] text-tenue num" style={{ gridTemplateColumns: `repeat(${lista.length}, minmax(0, 1fr))` }}>
        {lista.map((h, i) => (
          <span key={h.hora} className="text-center">
            {lista.length > 12 && i % 2 ? "" : String(h.hora).padStart(2, "0")}
          </span>
        ))}
      </div>
      <div className="grid text-[10.5px] num" style={{ gridTemplateColumns: `repeat(${lista.length}, minmax(0, 1fr))` }}>
        {lista.map((h) => (
          <span key={h.hora} className="text-center text-texto font-semibold">
            {h.pedidos || ""}
          </span>
        ))}
      </div>
      <small className="text-tenue text-[11px]">Arriba la plata, abajo la cantidad de pedidos de cada hora.</small>
    </div>
  );
}

function MasVendidos({ productos }) {
  if (!productos.length) return <p className="text-tenue text-sm">Todavía no se vendió nada.</p>;
  const max = productos[0].cantidad;
  return (
    <ol className="grid gap-2">
      {productos.map((p, i) => (
        <li key={p.nombre} className="grid grid-cols-[22px_1fr_auto] gap-x-2.5 items-center text-[13.5px]">
          <span className="text-tenue num text-right">{i + 1}</span>
          <span className="min-w-0">
            <span className="flex justify-between gap-2">
              <span className="truncate">{p.nombre}</span>
              <b className="num font-semibold">{p.cantidad}</b>
            </span>
            <span className="block h-1.5 rounded-full bg-gris mt-1 overflow-hidden">
              <span className="block h-full bg-naranja rounded-full" style={{ width: `${(p.cantidad / max) * 100}%` }} />
            </span>
          </span>
          <span className="num text-tenue w-[84px] text-right">{precio(p.total)}</span>
        </li>
      ))}
    </ol>
  );
}

function Historial({ fechaElegida, onElegir }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api
      .historial()
      .then(setDatos)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-naranja text-sm">No pudimos traer el historial: {error}</p>;
  if (!datos) return <Esqueleto alto="h-48" />;
  const max = Math.max(1, ...datos.dias.map((d) => d.vendido));
  const dias = [...datos.dias].reverse(); // el más nuevo arriba
  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <Cuadro titulo="Vendido en 30 días" valor={precio(datos.totales.vendido)} detalle={`MP ${precio(datos.totales.mercadopago)} · efectivo ${precio(datos.totales.efectivo_cobrado)}`} grande />
        <Cuadro titulo="Pedidos" valor={datos.totales.pedidos} detalle={`${datos.totales.cancelados} cancelados`} />
      </div>
      <ul className="grid gap-1">
        {dias.map((d) => (
          <li key={d.fecha}>
            <button
              type="button"
              onClick={() => onElegir(d.fecha)}
              className={`w-full grid grid-cols-[96px_1fr_auto] gap-2.5 items-center px-2 py-1.5 rounded-lg text-left text-[13px] hover:bg-carbon ${
                d.fecha === fechaElegida ? "bg-carbon ring-1 ring-naranja/60" : ""
              } ${d.pedidos ? "" : "text-tenue"}`}
            >
              <span className="truncate">{nombreDia(d.fecha)}</span>
              <span className="h-2.5 rounded-full bg-gris overflow-hidden">
                <span className="block h-full bg-naranja rounded-full" style={{ width: `${(d.vendido / max) * 100}%` }} />
              </span>
              <span className="num text-right w-[110px]">
                {d.pedidos ? (
                  <>
                    <b className="font-semibold">{precio(d.vendido)}</b> <small className="text-tenue">· {d.pedidos}</small>
                  </>
                ) : (
                  "—"
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Caja({ sesion }) {
  const esAdmin = sesion.usuario.rol === "admin";
  const [fecha, setFecha] = useState(null); // null = la jornada de hoy
  const [c, setC] = useState(null);
  const [hoy, setHoy] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [verHistorial, setVerHistorial] = useState(false);
  const [textoManual, setTextoManual] = useState(null);
  const { avisos, avisar } = useAvisos();

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const r = await api.dia(fecha);
      setC(r);
      if (!fecha) setHoy(r.fecha);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, [fecha]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Si es la de hoy, se actualiza sola cuando entra o cambia un pedido
  const esHoy = !fecha || fecha === hoy;
  const espera = useRef(null);
  const conectado = useEventosPanel(sesion.token, {
    onEvento: (m) => {
      if (!esHoy || !m.evento.startsWith("pedido_")) return;
      clearTimeout(espera.current);
      espera.current = setTimeout(cargar, 800);
    },
    onReconecta: () => esHoy && cargar(),
  });
  useEffect(() => () => clearTimeout(espera.current), []);

  async function copiarResumen() {
    const texto = textoResumen(c);
    if (await copiar(texto)) {
      setTextoManual(null);
      avisar("Resumen copiado, pegalo en WhatsApp");
    } else {
      setTextoManual(texto); // que lo copie a mano
    }
  }

  const modos = useMemo(() => Object.fromEntries((c?.por_modo || []).map((m) => [m.modo, m])), [c]);

  const elegirDia = (f) => {
    setFecha(f === hoy ? null : f);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <Marco sesion={sesion} derecha={<EnVivo conectado={conectado} />}>
      <AvisoConexion conectado={conectado} error={error} onReintentar={cargar} recargando={cargando} />
      <Titulo
        bajada={c ? `${nombreDia(c.fecha, !esHoy)}${esHoy ? " · la jornada de hoy, de 6 a 6" : " · de 6 a 6"}` : "La jornada va de las 6 de la mañana a las 6 del día siguiente."}
        derecha={
          <div className="flex flex-wrap items-center gap-2">
            {esAdmin && (
              <>
                <input
                  type="date"
                  className={`${claseInput} w-auto py-2 num`}
                  value={fecha || hoy || ""}
                  max={hoy || undefined}
                  onChange={(e) => e.target.value && setFecha(e.target.value === hoy ? null : e.target.value)}
                  aria-label="Elegir el día"
                />
                {!esHoy && (
                  <Boton secundario grande onClick={() => setFecha(null)}>
                    Hoy
                  </Boton>
                )}
              </>
            )}
            <Boton grande disabled={!c} onClick={copiarResumen}>
              Copiar resumen
            </Boton>
          </div>
        }
      >
        Caja{esHoy ? " del día" : ""}
      </Titulo>

      {textoManual && (
        <div className="mx-4 md:mx-6 mt-3 p-3 rounded-xl bg-carbon border border-linea grid gap-2">
          <small className="text-tenue">No pudimos copiarlo solo. Mantené apretado el texto y copialo:</small>
          <textarea readOnly rows={2} className={`${claseInput} text-sm`} value={textoManual} onFocus={(e) => e.target.select()} />
        </div>
      )}

      <div className={`px-4 md:px-6 py-4 pb-24 grid gap-4 transition-opacity ${cargando && c ? "opacity-60" : ""}`}>
        {!c ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Esqueleto key={i} alto="h-20" />
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
              <Cuadro grande titulo="Vendido" valor={precio(c.vendido)} detalle={`Mercado Pago ${precio(c.mercadopago)} · Efectivo ${precio(c.efectivo_cobrado)}`} />
              <Cuadro titulo="Efectivo a cobrar" valor={precio(c.efectivo_a_cobrar)} alerta={c.efectivo_a_cobrar > 0} detalle={c.efectivo_a_cobrar > 0 ? "Pedidos sin cobrar" : "Todo cobrado"} />
              <Cuadro titulo="Pedidos" valor={c.pedidos} detalle={`Ticket promedio ${precio(c.ticket_promedio)}`} />
              <Cuadro titulo="Comer adentro" valor={modos.comer_adentro?.pedidos ?? 0} detalle={precio(modos.comer_adentro?.total ?? 0)} />
              <Cuadro titulo="Take away" valor={modos.take_away?.pedidos ?? 0} detalle={precio(modos.take_away?.total ?? 0)} />
              <Cuadro
                titulo="Cancelados"
                valor={c.cancelados}
                detalle={c.mp_sin_pagar ? `+ ${c.mp_sin_pagar} de MP que no pagaron` : "Ninguno de MP sin pagar"}
              />
            </div>

            <div className="grid lg:grid-cols-2 gap-4 items-start">
              <section className="bg-negro border border-gris rounded-2xl p-4 grid gap-3">
                <h2 className="text-[24px]">Ventas por hora</h2>
                <VentasPorHora horas={c.por_hora} />
              </section>
              <section className="bg-negro border border-gris rounded-2xl p-4 grid gap-3">
                <h2 className="text-[24px]">Lo más vendido</h2>
                <MasVendidos productos={c.productos} />
              </section>
            </div>
          </>
        )}

        {esAdmin && (
          <section className="bg-negro border border-gris rounded-2xl p-4 grid gap-3">
            <button type="button" onClick={() => setVerHistorial((v) => !v)} aria-expanded={verHistorial} className="flex items-center justify-between text-left">
              <h2 className="text-[24px]">Últimos 30 días</h2>
              <span className="text-tenue text-sm">{verHistorial ? "▾ Ocultar" : "▸ Ver"}</span>
            </button>
            {verHistorial && <Historial fechaElegida={c?.fecha} onElegir={elegirDia} />}
          </section>
        )}
      </div>
      <Avisos avisos={avisos} />
    </Marco>
  );
}
