import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { pagos, tienda, ws } from "../api";
import Logo from "../componentes/Logo";
import { CLAVES, local } from "../lib/almacen";
import { horaDe, numeroPedido, precio, textoOpciones } from "../lib/formato";
import useSocket from "../lib/useSocket";

// Pantalla 5 de la maqueta: el cliente sigue su pedido en vivo

const VERIFICAR_CADA_MS = 5000;
const VERIFICAR_HASTA_MS = 2 * 60 * 1000;

const ORDEN = ["recibido", "en_preparacion", "listo", "entregado"];

function Paso({ titulo, bajada, hora: horaPaso, estado, ultimo }) {
  // estado: "hecho" | "ahora" | "pend"
  return (
    <li className="grid grid-cols-[24px_1fr_auto] gap-3 items-start relative pb-4 last:pb-0">
      {!ultimo && (
        <span className={`absolute left-[11px] top-6 bottom-0 w-0.5 ${estado === "hecho" ? "bg-naranja" : "bg-linea"}`} />
      )}
      <span
        className={`relative z-[1] w-6 h-6 rounded-full border-2 grid place-items-center text-xs ${
          estado === "hecho"
            ? "bg-naranja border-naranja text-white"
            : estado === "ahora"
              ? "border-naranja bg-negro shadow-[0_0_0_4px_rgba(240,92,43,0.14)]"
              : "border-linea bg-negro"
        }`}
      >
        {estado === "hecho" ? "✓" : estado === "ahora" ? <span className="w-2 h-2 rounded-full bg-naranja animate-pulse" /> : null}
      </span>
      <div className="leading-tight">
        <b className={`block text-sm ${estado === "pend" ? "text-tenue font-medium" : "font-semibold"}`}>{titulo}</b>
        {bajada && estado !== "pend" && <small className="text-tenue text-xs">{bajada}</small>}
      </div>
      <time className="text-tenue text-xs num">{horaPaso}</time>
    </li>
  );
}

function LineaDeTiempo({ pedido }) {
  const actual = ORDEN.indexOf(pedido.estado);
  const llevar = pedido.modo === "take_away";
  const pasos = [
    {
      titulo: "Recibido",
      bajada: pedido.metodo_pago === "mercadopago" ? "Pago aprobado" : "Lo pagás en efectivo",
    },
    { titulo: "En la plancha", bajada: "Lo estamos haciendo" },
    { titulo: "Listo", bajada: llevar ? "Retiralo en la cantina" : "Sale para tu lugar" },
    { titulo: llevar ? "Retirado" : "Entregado", bajada: "¡Que lo disfrutes!" },
  ];
  return (
    <ol className="bg-carbon rounded-2xl p-4 border border-gris">
      {pasos.map((p, i) => {
        const estado = i < actual || pedido.estado === "entregado" ? "hecho" : i === actual ? "ahora" : "pend";
        const horaPaso = i === 0 ? horaDe(pedido.created_at) : "";
        return <Paso key={p.titulo} {...p} estado={estado} hora={horaPaso} ultimo={i === pasos.length - 1} />;
      })}
    </ol>
  );
}

function frase(pedido) {
  const n = pedido.nombre.split(" ")[0];
  switch (pedido.estado) {
    case "pendiente_pago":
      return `${n}, falta confirmar el pago`;
    case "recibido":
      return `${n}, ya nos llegó tu pedido`;
    case "en_preparacion":
      return `${n}, ya lo estamos haciendo`;
    case "listo":
      return pedido.modo === "take_away" ? `${n}, ya está listo` : `${n}, ya sale para allá`;
    case "entregado":
      return `${n}, ¡que lo disfrutes!`;
    case "cancelado":
      return `${n}, tu pedido se canceló`;
    default:
      return "";
  }
}

function Pago({ pedido }) {
  const mp = pedido.metodo_pago === "mercadopago";
  const pagado = pedido.estado_pago === "aprobado";
  let texto;
  if (pagado) texto = mp ? "✓ Pagado con Mercado Pago" : "✓ Pagado en efectivo";
  else if (mp) texto = "Pago pendiente";
  else texto = pedido.modo === "take_away" ? "Efectivo · pagás al retirar" : "Efectivo · pagás al recibirlo";
  return (
    <div className="flex justify-between text-sm px-0.5 num">
      <span className={pagado ? "text-ok font-semibold" : "text-alerta font-semibold"}>{texto}</span>
      <b>{precio(pedido.total)}</b>
    </div>
  );
}

function Items({ pedido }) {
  return (
    <details className="bg-carbon rounded-2xl border border-gris px-4 py-3 text-sm">
      <summary className="cursor-pointer text-tenue">Ver lo que pediste</summary>
      <ul className="mt-2 grid gap-1.5">
        {pedido.items.map((it, i) => (
          <li key={i}>
            <div className="flex justify-between gap-3 num">
              <span>
                {it.cantidad}× {it.nombre_producto}
              </span>
              <span>{precio(it.precio_unitario * it.cantidad)}</span>
            </div>
            {it.opciones.length > 0 && <small className="block text-tenue text-xs">{textoOpciones(it.opciones)}</small>}
            {it.nota && <small className="block text-naranja text-xs">{it.nota}</small>}
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function Seguimiento() {
  const { codigo } = useParams();
  const [params] = useSearchParams();
  const [pedido, setPedido] = useState(null);
  const [error, setError] = useState(null);
  const [verificando, setVerificando] = useState(false);
  const [sinConfirmar, setSinConfirmar] = useState(params.get("pago") === "error");
  const [pagando, setPagando] = useState(false);
  const [errorPago, setErrorPago] = useState(null);
  const estadoAnterior = useRef(null);

  const cargar = useCallback(async () => {
    try {
      setPedido(await tienda.pedido(codigo));
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, [codigo]);

  useEffect(() => {
    cargar();
    // Así si cierra y vuelve a abrir la tienda, le aparece "Ver mi pedido"
    const ultimo = local.leer(CLAVES.ultimoPedido);
    if (ultimo?.codigo !== codigo) local.guardar(CLAVES.ultimoPedido, { codigo, creado: Date.now() });
  }, [codigo, cargar]);

  const enPendientePago = pedido?.estado === "pendiente_pago";
  const rechazado = enPendientePago && pedido?.estado_pago === "rechazado";

  // Volvió de Mercado Pago: le preguntamos al backend si ya se pagó,
  // cada 5 segundos, hasta que cambie o pasen 2 minutos.
  // Arranca solo al entrar (aunque antes lo hayan rechazado: capaz volvió a pagar)
  // y de nuevo con "Ya pagué, revisar de nuevo"
  const [ciclo, setCiclo] = useState(0);
  useEffect(() => {
    if (ciclo === 0 && enPendientePago && params.get("pago") !== "error") setCiclo(1);
  }, [ciclo, enPendientePago, params]);

  useEffect(() => {
    if (ciclo === 0) return undefined;
    let fin = false;
    let timer;
    const arranque = Date.now();
    setVerificando(true);
    setSinConfirmar(false);

    async function verificar() {
      try {
        const p = await pagos.verificar(codigo);
        if (fin) return;
        setPedido(p);
        if (p.estado !== "pendiente_pago" || p.estado_pago === "rechazado") {
          setVerificando(false);
          return;
        }
      } catch {
        // MP no respondió: seguimos probando hasta el límite
      }
      if (fin) return;
      if (Date.now() - arranque >= VERIFICAR_HASTA_MS) {
        setVerificando(false);
        setSinConfirmar(true);
        return;
      }
      timer = setTimeout(verificar, VERIFICAR_CADA_MS);
    }
    verificar();
    return () => {
      fin = true;
      clearTimeout(timer);
    };
  }, [codigo, ciclo]);

  // En vivo mientras el pedido está en curso
  const activo = pedido && !["entregado", "cancelado"].includes(pedido.estado);
  const conectado = useSocket(activo ? ws.pedido(codigo) : null, {
    onMensaje: (m) => m.pedido && setPedido(m.pedido),
    onReconecta: cargar,
  });

  // Take away listo: que vibre el celu (una sola vez)
  useEffect(() => {
    if (!pedido) return;
    if (estadoAnterior.current && estadoAnterior.current !== "listo" && pedido.estado === "listo" && pedido.modo === "take_away") {
      try {
        navigator.vibrate?.([300, 120, 300, 120, 500]);
      } catch {
        // no todos los celus dejan
      }
    }
    estadoAnterior.current = pedido.estado;
  }, [pedido]);

  async function volverAPagar() {
    setPagando(true);
    setErrorPago(null);
    try {
      const { link_pago } = await pagos.preferencia(codigo);
      window.location.assign(link_pago);
    } catch (e) {
      setErrorPago(e.message);
      setPagando(false);
    }
  }

  const arriba = (
    <header className="flex items-center justify-between px-4 pt-3 pb-1">
      <Link to="/" aria-label="Ir a la carta">
        <Logo />
      </Link>
      {activo && (
        <div className="text-[11.5px] text-tenue text-right leading-tight">
          {conectado ? (
            <>
              Se actualiza<b className="block text-texto font-semibold">solo</b>
            </>
          ) : (
            <b className="block text-alerta font-semibold">Reconectando...</b>
          )}
        </div>
      )}
    </header>
  );

  if (error) {
    return (
      <div className="max-w-[560px] mx-auto min-h-dvh">
        {arriba}
        <div className="mx-4 mt-10 p-5 rounded-2xl bg-carbon border border-linea text-center grid gap-3 justify-items-center">
          <p className="font-display text-2xl">{error.status === 404 ? "No encontramos ese pedido" : "No pudimos cargar tu pedido"}</p>
          <p className="text-tenue text-sm">{error.status === 404 ? "Revisá el link o volvé a la carta." : error.message}</p>
          <div className="flex gap-2">
            {error.status !== 404 && (
              <button type="button" onClick={cargar} className="px-5 py-2.5 rounded-xl bg-naranja font-semibold">
                Reintentar
              </button>
            )}
            <Link to="/" className="px-5 py-2.5 rounded-xl bg-gris font-semibold">
              Ir a la carta
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!pedido) {
    return (
      <div className="max-w-[560px] mx-auto min-h-dvh">
        {arriba}
        <div className="px-4 mt-4 grid gap-3 animate-pulse" aria-label="Cargando tu pedido">
          <div className="h-4 w-24 mx-auto rounded bg-gris" />
          <div className="h-16 w-40 mx-auto rounded bg-gris" />
          <div className="h-48 rounded-2xl bg-carbon" />
          <div className="h-16 rounded-2xl bg-carbon" />
        </div>
      </div>
    );
  }

  const listoParaRetirar = pedido.estado === "listo" && pedido.modo === "take_away";

  return (
    <div className="max-w-[560px] mx-auto min-h-dvh pb-8">
      {arriba}
      <div className="px-4 flex flex-col gap-3">
        <div className="text-center pt-2">
          <small className="text-tenue text-xs tracking-[0.2em] uppercase">Tu pedido</small>
          <h1 className="text-[80px] text-naranja num leading-none">{numeroPedido(pedido.numero)}</h1>
          <p className="text-[15px]">{frase(pedido)}</p>
        </div>

        {listoParaRetirar && (
          <div role="alert" className="rounded-2xl bg-ok text-[#062814] p-4 text-center animate-[aparecer_.3s_ease-out]">
            <p className="font-display text-[34px] leading-none">¡Ya podés retirarlo!</p>
            <p className="text-sm font-semibold mt-1">Acercate a la cantina y decí el {numeroPedido(pedido.numero)}</p>
          </div>
        )}

        {enPendientePago && verificando && (
          <div role="status" className="rounded-2xl bg-mp/15 border border-mp/40 p-4 text-center">
            <p className="font-semibold">Confirmando tu pago...</p>
            <p className="text-tenue text-xs mt-1">Puede tardar unos segundos. No cierres esta pantalla.</p>
          </div>
        )}

        {enPendientePago && !verificando && (rechazado || sinConfirmar) && (
          <div role="alert" className="rounded-2xl bg-carbon border border-linea p-4 grid gap-3">
            <p className="text-sm">
              {rechazado
                ? "El pago no se aprobó. Podés probar de nuevo con otra tarjeta o medio de pago."
                : "Todavía no nos llegó la confirmación del pago. Si no pagaste, podés hacerlo ahora."}
            </p>
            {errorPago && <p className="text-naranja text-sm">{errorPago}</p>}
            <button
              type="button"
              onClick={volverAPagar}
              disabled={pagando}
              className="rounded-xl py-3 font-bold text-sm bg-mp text-white disabled:opacity-60"
            >
              {pagando ? "YENDO A MERCADO PAGO..." : "PAGAR CON MERCADO PAGO"}
            </button>
            {!rechazado && (
              <button type="button" onClick={() => setCiclo((c) => c + 1)} className="text-tenue text-sm underline underline-offset-2">
                Ya pagué, revisar de nuevo
              </button>
            )}
          </div>
        )}

        {pedido.estado === "cancelado" ? (
          <div className="rounded-2xl bg-carbon border border-linea p-4 text-sm grid gap-1">
            <b>Este pedido se canceló.</b>
            <span className="text-tenue">
              {pedido.estado_pago === "aprobado" && pedido.metodo_pago === "mercadopago"
                ? "Si ya lo habías pagado, acercate a la cantina para que te devolvamos la plata."
                : "Si creés que es un error, acercate a la cantina."}
            </span>
          </div>
        ) : (
          !enPendientePago && <LineaDeTiempo pedido={pedido} />
        )}

        <div className="rounded-2xl bg-naranja/14 border border-naranja/40 px-4 py-3">
          <small className="text-naranja font-semibold text-[11px] tracking-[0.12em] uppercase">
            {pedido.modo === "take_away" ? "Lo retirás en" : "Te lo llevamos a"}
          </small>
          <b className="block font-display font-normal text-[28px] tracking-wide leading-tight">
            {pedido.modo === "take_away" ? "La cantina" : pedido.ubicacion}
          </b>
        </div>

        <Pago pedido={pedido} />
        <Items pedido={pedido} />

        {pedido.modo === "comer_adentro" && activo && (
          <p className="text-tenue text-xs text-center">Si te movés de lugar, avisá en la cantina.</p>
        )}
        <Link to="/" className="text-center text-naranja text-sm font-semibold py-2">
          {activo ? "Volver a la carta" : "Hacer otro pedido"}
        </Link>
      </div>
    </div>
  );
}
