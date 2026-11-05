import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { panel } from "../api";
import Logo from "../componentes/Logo";
import { haceCuanto, minutosDesde, numeroPedido, precio, telefono, textoOpciones } from "../lib/formato";
import useSonido from "../lib/sonido";
import { NOMBRE_ROL, useSalir } from "./sesion";
import usePedidosEnVivo, { useAhora } from "./usePedidosEnVivo";

// Panel de la cantina (parte 2 de la maqueta)

const ACTIVOS = ["recibido", "en_preparacion", "listo"];
const COLUMNAS = [
  { estado: "recibido", titulo: "Nuevos", corto: "Nuevos" },
  { estado: "en_preparacion", titulo: "En preparación", corto: "Preparando" },
  { estado: "listo", titulo: "Listos para llevar", corto: "Listos" },
];
const TARDE_MIN = 15; // a partir de acá el "hace X min" se pone amarillo

// ---------- avisitos de abajo (ej: "Acordate de devolver el pago") ----------

function useAvisos() {
  const [avisos, setAvisos] = useState([]);
  const avisar = useCallback((texto, tipo = "ok") => {
    const id = Math.random();
    setAvisos((a) => [...a, { id, texto, tipo }]);
    setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), tipo === "alerta" ? 9000 : 4000);
  }, []);
  return { avisos, avisar };
}

function Avisos({ avisos }) {
  return (
    <div className="fixed bottom-4 inset-x-0 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none" aria-live="polite">
      {avisos.map((a) => (
        <div
          key={a.id}
          className={`max-w-md w-full rounded-xl px-4 py-3 text-sm font-semibold shadow-lg ${
            a.tipo === "alerta" ? "bg-alerta text-[#2a1d02]" : a.tipo === "error" ? "bg-naranja text-white" : "bg-gris text-texto"
          }`}
        >
          {a.texto}
        </div>
      ))}
    </div>
  );
}

// ---------- tarjeta de un pedido ----------

function Cobro({ p }) {
  if (p.metodo_pago === "mercadopago") {
    return <span className="text-[12px] font-semibold px-2 py-1 rounded-md bg-ok/15 text-ok num">MP pagado · {precio(p.total)}</span>;
  }
  if (p.estado_pago === "aprobado") {
    return <span className="text-[12px] font-semibold px-2 py-1 rounded-md bg-ok/15 text-ok num">Efectivo cobrado · {precio(p.total)}</span>;
  }
  return <span className="text-[12px] font-semibold px-2 py-1 rounded-md bg-alerta/15 text-alerta num">Cobrar · {precio(p.total)}</span>;
}

function Boton({ children, secundario = false, peligro = false, ...props }) {
  return (
    <button
      type="button"
      {...props}
      className={`text-[13px] font-semibold px-3 py-2 rounded-lg whitespace-nowrap disabled:opacity-50 ${
        peligro ? "bg-naranja/15 text-naranja" : secundario ? "bg-gris text-texto" : "bg-naranja text-white"
      }`}
    >
      {children}
    </button>
  );
}

function TarjetaPedido({ p, nuevo, ahora, onActualizado, avisar }) {
  const [ocupado, setOcupado] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [error, setError] = useState(null);
  const enCurso = useRef(false); // así dos toques rápidos no mandan dos veces

  async function hacer(accion, textoOk) {
    if (enCurso.current) return;
    enCurso.current = true;
    setOcupado(true);
    setError(null);
    try {
      const actualizado = await accion();
      onActualizado(actualizado);
      if (actualizado.aviso) avisar(actualizado.aviso, "alerta");
      else if (textoOk) avisar(textoOk);
      setConfirmando(false);
    } catch (e) {
      setError(e.message);
    } finally {
      enCurso.current = false;
      setOcupado(false);
    }
  }

  const mover = (estado, texto) => hacer(() => panel.cambiarEstado(p.id, estado), texto);
  const sinCobrar = p.metodo_pago === "efectivo" && p.estado_pago !== "aprobado";
  const minutos = minutosDesde(p.created_at, ahora);
  const tiempo = p.estado === "listo" ? `listo ${haceCuanto(p.updated_at, ahora)}` : haceCuanto(p.created_at, ahora);
  const tarde = p.estado !== "listo" && minutos >= TARDE_MIN;
  const n = numeroPedido(p.numero);

  return (
    <article
      className={`bg-negro border rounded-2xl p-3.5 grid gap-2 transition-shadow ${
        nuevo ? "border-naranja shadow-[0_0_0_3px_rgba(240,92,43,0.25),0_0_24px_rgba(240,92,43,0.35)] animate-pulse" : "border-gris"
      }`}
    >
      <div className="flex justify-between items-center">
        <b className="font-display font-normal text-[30px] tracking-wide leading-none num">{n}</b>
        <time className={`text-xs num ${tarde ? "text-alerta font-semibold" : "text-tenue"}`}>{tiempo}</time>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={`text-[10.5px] font-bold tracking-wider uppercase px-2 py-1 rounded ${
            p.modo === "comer_adentro" ? "bg-naranja text-white" : "border border-texto"
          }`}
        >
          {p.modo === "comer_adentro" ? "Comer adentro" : "Take away"}
        </span>
        {!p.impreso_at && p.estado !== "listo" && <span className="text-[11px] text-tenue">🖨 comanda sin imprimir</span>}
      </div>
      {p.modo === "comer_adentro" && (
        <div className="font-display text-[26px] tracking-wide leading-[1.05] break-words">{p.ubicacion}</div>
      )}
      <div className="text-tenue text-[13px]">
        {p.nombre} {p.apellido} ·{" "}
        <a href={`tel:${p.telefono}`} className="underline-offset-2 hover:underline num">
          {telefono(p.telefono)}
        </a>
      </div>
      <ul className="text-[13.5px] border-t border-dashed border-linea pt-2 grid gap-1">
        {p.items.map((it, i) => (
          <li key={i}>
            <span className="num">{it.cantidad}×</span> {it.nombre_producto}
            {it.opciones.length > 0 && <small className="block text-tenue pl-5 text-[12.5px]">{textoOpciones(it.opciones)}</small>}
            {it.nota && <small className="block text-naranja pl-5 text-[12.5px] font-semibold">{it.nota}</small>}
          </li>
        ))}
        {p.notas && <li className="text-naranja text-[12.5px] font-semibold">Nota: {p.notas}</li>}
      </ul>

      <div className="flex justify-between items-center gap-2 flex-wrap">
        <Cobro p={p} />
      </div>

      {error && (
        <p role="alert" className="text-naranja text-[13px]">
          {error}
        </p>
      )}

      {confirmando ? (
        <div className="rounded-xl bg-naranja/10 border border-naranja/40 p-2.5 grid gap-2">
          <p className="text-sm font-semibold">¿Cancelar el {n}? No se puede deshacer.</p>
          <div className="flex gap-2 justify-end">
            <Boton secundario disabled={ocupado} onClick={() => setConfirmando(false)}>
              No, dejalo
            </Boton>
            <Boton disabled={ocupado} onClick={() => mover("cancelado", `${n} cancelado`)}>
              {ocupado ? "Cancelando..." : "Sí, cancelar"}
            </Boton>
          </div>
        </div>
      ) : (
        <div className="flex gap-1.5 flex-wrap justify-end">
          <Boton peligro disabled={ocupado} onClick={() => setConfirmando(true)} aria-label={`Cancelar el ${n}`}>
            Cancelar
          </Boton>
          {p.estado !== "listo" && (
            <Boton secundario disabled={ocupado} onClick={() => hacer(() => panel.reimprimir(p.id), `${n}: la comanda sale de nuevo`)} title="Reimprimir la comanda">
              🖨 Reimprimir
            </Boton>
          )}
          {sinCobrar && p.estado !== "listo" && (
            <Boton secundario disabled={ocupado} onClick={() => hacer(() => panel.cobrar(p.id), `${n} cobrado`)}>
              Cobrar
            </Boton>
          )}
          {p.estado === "recibido" && (
            <Boton disabled={ocupado} onClick={() => mover("en_preparacion")}>
              A la cocina
            </Boton>
          )}
          {p.estado === "en_preparacion" && (
            <Boton disabled={ocupado} onClick={() => mover("listo")}>
              Listo
            </Boton>
          )}
          {p.estado === "listo" &&
            (sinCobrar ? (
              <Boton disabled={ocupado} onClick={() => hacer(() => panel.cobrarYEntregar(p.id), `${n} cobrado y entregado`)}>
                Cobrar {precio(p.total)} y entregar
              </Boton>
            ) : (
              <Boton disabled={ocupado} onClick={() => mover("entregado", `${n} entregado`)}>
                Entregado
              </Boton>
            ))}
        </div>
      )}
    </article>
  );
}

// ---------- la pantalla ----------

function Resumen({ datos }) {
  const cuadros = [
    { titulo: "Pedidos hoy", valor: datos ? datos.pedidos : "–" },
    { titulo: "Vendido hoy", valor: datos ? precio(datos.vendido) : "–" },
    { titulo: "Efectivo a cobrar", valor: datos ? precio(datos.efectivo_a_cobrar) : "–", alerta: true },
    { titulo: "Esperando pago de MP", valor: datos ? datos.esperando_pago_mp : "–" },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 md:gap-3 px-4 md:px-6 pt-4">
      {cuadros.map((c) => (
        <div key={c.titulo} className="bg-negro border border-gris rounded-xl px-3.5 py-2.5">
          <small className="text-tenue text-[11.5px] block">{c.titulo}</small>
          <b className={`text-[20px] md:text-[22px] font-bold num ${c.alerta && datos?.efectivo_a_cobrar > 0 ? "text-alerta" : ""}`}>{c.valor}</b>
        </div>
      ))}
    </div>
  );
}

export function EnVivo({ conectado }) {
  return conectado ? (
    <span className="inline-flex items-center gap-1.5 text-ok font-semibold text-xs whitespace-nowrap">
      <span className="w-2 h-2 rounded-full bg-ok shadow-[0_0_0_3px_rgba(61,190,122,0.2)]" />
      En vivo
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-alerta font-semibold text-xs whitespace-nowrap">
      <span className="w-2 h-2 rounded-full bg-alerta animate-pulse" />
      Reconectando
    </span>
  );
}

export function AvisoConexion({ conectado, error, onReintentar }) {
  if (conectado && !error) return null;
  return (
    <div role="alert" className="bg-alerta text-[#2a1d02] text-sm font-semibold px-4 py-2 flex items-center justify-between gap-3">
      <span>
        {!conectado
          ? "Se cortó la conexión en vivo. Estamos reconectando: los pedidos nuevos pueden tardar en aparecer."
          : `No pudimos traer los pedidos: ${error}`}
      </span>
      <button type="button" onClick={onReintentar} className="underline whitespace-nowrap">
        Recargar
      </button>
    </div>
  );
}

export function AvisoSonido({ habilitado }) {
  if (habilitado) return null;
  return (
    <button type="button" className="w-full bg-naranja text-white text-sm font-semibold px-4 py-2">
      🔔 Tocá acá para activar el sonido de pedidos nuevos
    </button>
  );
}

export default function Panel({ sesion }) {
  const salir = useSalir();
  const { sonar, habilitado } = useSonido();
  const ahora = useAhora(30000);
  const { avisos, avisar } = useAvisos();
  const [resumen, setResumen] = useState(null);
  const [pestania, setPestania] = useState("recibido");

  const cargarResumen = useCallback(() => {
    panel.resumen().then(setResumen).catch(() => {});
  }, []);

  const { lista, cargando, error, conectado, recargar, actualizar, destacados } = usePedidosEnVivo(sesion.token, ACTIVOS, {
    onNuevo: sonar,
  });

  // El resumen se recalcula cada vez que cambia algo (y cada minuto por las dudas)
  const firma = lista.map((p) => `${p.id}:${p.estado}:${p.estado_pago}`).join(",");
  useEffect(() => {
    const t = setTimeout(cargarResumen, 400);
    return () => clearTimeout(t);
  }, [firma, cargarResumen]);
  useEffect(() => {
    const t = setInterval(cargarResumen, 60000);
    return () => clearInterval(t);
  }, [cargarResumen]);

  const usuario = sesion.usuario;

  return (
    <div className="min-h-dvh bg-carbon">
      <AvisoConexion conectado={conectado} error={error} onReintentar={recargar} />
      <AvisoSonido habilitado={habilitado} />

      <header className="flex items-center gap-4 md:gap-7 px-4 md:px-6 py-3 border-b border-gris bg-negro">
        <Logo chico />
        <nav className="flex gap-1 flex-1">
          <span className="px-3 py-1.5 rounded-lg bg-gris text-sm font-medium">Pedidos</span>
          <Link to="/cocina" className="px-3 py-1.5 rounded-lg text-tenue text-sm font-medium hover:text-texto">
            Cocina
          </Link>
        </nav>
        <div className="flex items-center gap-3 text-[12.5px] text-tenue">
          <EnVivo conectado={conectado} />
          <span className="hidden sm:inline">
            {NOMBRE_ROL[usuario.rol]} · {usuario.nombre}
          </span>
          <button type="button" onClick={salir} className="text-tenue hover:text-texto underline-offset-2 hover:underline">
            Salir
          </button>
        </div>
      </header>

      <Resumen datos={resumen} />

      {/* En el celu las columnas pasan a pestañas */}
      <div className="md:hidden flex gap-1 px-4 pt-4" role="tablist">
        {COLUMNAS.map((c) => {
          const cant = lista.filter((p) => p.estado === c.estado).length;
          return (
            <button
              key={c.estado}
              type="button"
              role="tab"
              aria-selected={pestania === c.estado}
              onClick={() => setPestania(c.estado)}
              className={`flex-1 rounded-lg py-2 text-[13px] font-semibold ${pestania === c.estado ? "bg-naranja text-white" : "bg-negro text-tenue border border-gris"}`}
            >
              {c.corto} <span className="num opacity-80">· {cant}</span>
            </button>
          );
        })}
      </div>

      <main className="grid md:grid-cols-3 gap-4 px-4 md:px-6 pt-4 pb-24 items-start">
        {COLUMNAS.map((c) => {
          const pedidos = lista.filter((p) => p.estado === c.estado);
          return (
            <section key={c.estado} className={`grid gap-2.5 ${pestania === c.estado ? "" : "hidden md:grid"}`}>
              <div className="hidden md:flex items-center justify-between px-0.5">
                <h3 className={`text-[24px] ${c.estado === "recibido" ? "text-naranja" : ""}`}>{c.titulo}</h3>
                <span className="bg-gris rounded-full px-2.5 text-xs font-semibold num">{pedidos.length}</span>
              </div>
              {cargando ? (
                <div className="h-40 rounded-2xl bg-negro border border-gris animate-pulse" />
              ) : pedidos.length === 0 ? (
                <p className="text-tenue text-sm px-1 py-6 text-center border border-dashed border-gris rounded-2xl">Nada por acá</p>
              ) : (
                pedidos.map((p) => (
                  <TarjetaPedido key={p.id} p={p} nuevo={destacados.has(p.id)} ahora={ahora} onActualizado={actualizar} avisar={avisar} />
                ))
              )}
            </section>
          );
        })}
      </main>

      <Avisos avisos={avisos} />
    </div>
  );
}
