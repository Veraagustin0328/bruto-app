import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { pagos, tienda } from "../api";
import { Campo, Radio, Stepper, claseInput } from "../componentes/Controles";
import { CANCHAS, LINK_PEDIDOSYA } from "../config";
import { CLAVES, local, sesion } from "../lib/almacen";
import { llaveDelIntento, olvidarIntento } from "../lib/llave";
import { recordarPedido } from "../lib/misPedidos";
import { precio, textoOpciones } from "../lib/formato";
import { useCarrito } from "./carrito";

// Pantallas 3 y 4 de la maqueta: "Tu pedido" (dónde lo comés) y "Tus datos" (y pago)

const MODOS = [
  { id: "comer_adentro", nombre: "Comer adentro", bajada: "Te lo llevamos" },
  { id: "take_away", nombre: "Take away", bajada: "Retirás en la cantina" },
  { id: "delivery", nombre: "Delivery", bajada: "Por PedidosYa" },
];

function Volver({ titulo, onVolver }) {
  return (
    <div className="sticky top-0 z-10 bg-negro/95 backdrop-blur flex items-center gap-3 px-4 pt-3 pb-3">
      <button
        type="button"
        onClick={onVolver}
        aria-label="Volver"
        className="w-9 h-9 rounded-full bg-gris grid place-items-center text-xl leading-none"
      >
        ‹
      </button>
      <h3 className="text-[28px]">{titulo}</h3>
    </div>
  );
}

function Pregunta({ children }) {
  return <h4 className="font-display text-[24px] tracking-wide mt-2">{children}</h4>;
}

function Total({ total }) {
  return (
    <div className="flex justify-between items-baseline pt-1 num">
      <span className="text-tenue">Total</span>
      <b className="text-[22px] font-bold">{precio(total)}</b>
    </div>
  );
}

function BotonFijo({ children, mp = false, ...props }) {
  return (
    <div className="sticky bottom-0 z-10 bg-gradient-to-t from-negro via-negro to-negro/0 px-3 pt-4 pb-[max(14px,env(safe-area-inset-bottom))]">
      <button
        type="button"
        {...props}
        className={`w-full rounded-2xl py-3.5 font-bold tracking-wide text-sm text-white disabled:opacity-60 ${
          mp ? "bg-mp" : "bg-naranja"
        }`}
      >
        {children}
      </button>
    </div>
  );
}

function ItemCarrito({ item }) {
  const { cambiarCantidad, quitar, MAX_CANTIDAD } = useCarrito();
  const opciones = textoOpciones(item.opciones);
  const tachado = item.problema ? "line-through text-tenue" : "";
  return (
    <div className="py-3 border-b border-gris grid gap-1.5">
      <div className="flex justify-between gap-3 num">
        <b className={`font-semibold ${tachado}`}>
          {item.cantidad}× {item.nombre}
        </b>
        <span className={`font-semibold ${tachado}`}>{precio(item.precio_unitario * item.cantidad)}</span>
      </div>
      {item.problema && (
        <p className="text-[13px] font-semibold text-naranja bg-naranja/10 rounded-lg px-2.5 py-1.5">
          {item.problema}. Sacalo para poder seguir.
        </p>
      )}
      {opciones && <p className="text-tenue text-[13px] leading-snug">{opciones}</p>}
      {item.nota && <p className="text-naranja text-[13px] leading-snug">{item.nota}</p>}
      <div className="flex items-center justify-between mt-0.5">
        <Stepper
          valor={item.cantidad}
          etiqueta={item.nombre}
          puedeMas={item.cantidad < MAX_CANTIDAD}
          onMenos={() => cambiarCantidad(item.id, item.cantidad - 1)}
          onMas={() => cambiarCantidad(item.id, item.cantidad + 1)}
        />
        <button type="button" onClick={() => quitar(item.id)} className="text-tenue text-[13px] underline underline-offset-2 px-1 py-1">
          Sacar
        </button>
      </div>
    </div>
  );
}

function OpcionPago({ on, onElegir, logo, colorLogo, titulo, bajada }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={on}
      onClick={onElegir}
      className={`w-full text-left flex items-center gap-3 p-3 rounded-xl bg-carbon border ${on ? "border-naranja" : "border-gris"}`}
    >
      <span className={`w-10 h-10 rounded-lg grid place-items-center font-bold text-xs flex-none ${colorLogo}`}>{logo}</span>
      <span className="flex-1 leading-tight">
        <b className="block text-sm font-semibold">{titulo}</b>
        <small className="text-tenue text-xs">{bajada}</small>
      </span>
      <Radio on={on} />
    </button>
  );
}

// Lo que va cargando en el checkout se guarda en la pestaña: si toca
// "+ Agregar algo más" y vuelve, sigue todo como lo dejó
function leerBorrador() {
  return sesion.leer(CLAVES.borrador, {}) || {};
}

export default function Checkout({ paso, irA, donde, estadoTienda }) {
  const navigate = useNavigate();
  const { items, total, vaciar, repasar, conProblema } = useCarrito();
  const [borrador] = useState(leerBorrador);
  const guardados = local.leer(CLAVES.datos, {}) || {};

  const [modo, setModo] = useState(borrador.modo || "comer_adentro");
  // Si vino del QR de una cancha, gana el QR
  const [ubicacion, setUbicacion] = useState(donde || borrador.ubicacion || "");
  const [nombre, setNombre] = useState(borrador.nombre ?? guardados.nombre ?? "");
  const [apellido, setApellido] = useState(borrador.apellido ?? guardados.apellido ?? "");
  const [telefono, setTelefono] = useState(borrador.telefono ?? guardados.telefono ?? "");
  const [metodo, setMetodo] = useState(borrador.metodo || "mercadopago");
  const [errores, setErrores] = useState({});
  const [errorEnvio, setErrorEnvio] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [preciosNuevos, setPreciosNuevos] = useState(0);
  const enviandoRef = useRef(false); // para que dos toques rápidos no manden dos pedidos

  useEffect(() => {
    sesion.guardar(CLAVES.borrador, { modo, ubicacion, nombre, apellido, telefono, metodo });
  }, [modo, ubicacion, nombre, apellido, telefono, metodo]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [paso]);

  // Al entrar al checkout traigo la carta de ahora: si Renzo cambió precios o
  // se apagó algo mientras el pedido estaba en el carrito, se ve acá y no
  // recién en Mercado Pago. El precio que vale igual lo calcula el backend
  const repasarRef = useRef(repasar);
  repasarRef.current = repasar;
  const revisarCarta = useCallback(async () => {
    try {
      const cambiaron = repasarRef.current(await tienda.menu());
      if (cambiaron) setPreciosNuevos(cambiaron);
    } catch {
      // sin internet: sigue con lo que tenía, el backend igual valida todo
    }
  }, []);
  useEffect(() => {
    revisarCarta();
  }, [paso, revisarCarta]);

  const linkDelivery = estadoTienda?.link_delivery || LINK_PEDIDOSYA;
  const cerrada = estadoTienda && !estadoTienda.acepta_pedidos;
  const textoCerrada = estadoTienda?.abierto && estadoTienda?.pausado ? "PEDIDOS EN PAUSA" : "CANTINA CERRADA";

  function continuar() {
    if (cerrada || conProblema.length) return;
    const e = {};
    if (modo === "comer_adentro" && ubicacion.trim().length < 3) {
      e.ubicacion = "Decinos dónde estás así te lo llevamos";
    }
    setErrores(e);
    if (!Object.keys(e).length) irA("datos");
  }

  async function confirmar() {
    if (enviandoRef.current) return;
    const e = {};
    if (nombre.trim().length < 2) e.nombre = "Poné tu nombre";
    if (apellido.trim().length < 2) e.apellido = "Poné tu apellido";
    const digitos = telefono.replace(/\D/g, "");
    if (digitos.length < 8 || digitos.length > 15) e.telefono = "Revisá el teléfono, con característica (ej: 261 555 0142)";
    setErrores(e);
    if (Object.keys(e).length) return;

    enviandoRef.current = true;
    setEnviando(true);
    setErrorEnvio(null);

    let pedido;
    try {
      // Misma llave mientras no entre: si se cortó la señal y reintenta, no se duplica
      pedido = await tienda.crearPedido({
        modo,
        ubicacion: modo === "comer_adentro" ? ubicacion.trim() : null,
        nombre: nombre.trim(),
        apellido: apellido.trim(),
        telefono: telefono.trim(),
        metodo_pago: metodo,
        notas: null,
        items: items.map((i) => ({
          producto_id: i.producto_id,
          cantidad: i.cantidad,
          nota: i.nota,
          opciones: i.opciones.map((o) => ({ opcion_id: o.opcion_id, cantidad: o.cantidad })),
        })),
      }, llaveDelIntento());
    } catch (err) {
      // Si fue por algo de la carta (se apagó un producto, cambió algo), repaso
      // el carrito así en "Tu pedido" se marca cuál es
      if (err.status === 400) revisarCarta();
      // El backend ya manda el mensaje escrito para el cliente. Sin conexión no
      // sabemos si llegó: puede tocar de nuevo tranquilo, con la misma llave no se duplica
      setErrorEnvio(
        err.status === 0
          ? "Se cortó la señal y no sabemos si tu pedido llegó. Tocá el botón de nuevo: si ya había entrado, no se duplica."
          : err.message,
      );
      setEnviando(false);
      enviandoRef.current = false;
      return;
    }

    // El pedido ya existe: guardo lo que sirve para la próxima y vacío el carrito.
    // La llave ya cumplió: el próximo pedido lleva otra
    olvidarIntento();
    local.guardar(CLAVES.datos, { nombre: nombre.trim(), apellido: apellido.trim(), telefono: telefono.trim() });
    recordarPedido(pedido.codigo);
    sesion.guardar(CLAVES.borrador, null);
    vaciar();

    if (metodo === "efectivo") {
      navigate(`/pedido/${pedido.codigo}`, { replace: true });
      return;
    }

    try {
      const { link_pago } = await pagos.preferencia(pedido.codigo);
      window.location.assign(link_pago);
    } catch {
      // Si MP no responde, desde el seguimiento puede volver a intentar el pago
      navigate(`/pedido/${pedido.codigo}?pago=error`, { replace: true });
    }
  }

  if (!items.length) {
    return (
      <div className="min-h-dvh flex flex-col">
        <Volver titulo="Tu pedido" onVolver={() => irA(null)} />
        <div className="flex-1 grid place-items-center px-6 text-center">
          <div className="grid gap-3 justify-items-center">
            <p className="font-display text-3xl">Tu pedido está vacío</p>
            <p className="text-tenue text-sm">Elegí algo de la carta y volvé acá.</p>
            <button type="button" onClick={() => irA(null)} className="mt-2 px-5 py-2.5 rounded-xl bg-naranja font-semibold">
              Ver la carta
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------- paso 1: tu pedido + dónde lo comés ----------
  if (paso === "pedido") {
    return (
      <div className="min-h-dvh flex flex-col">
        <Volver titulo="Tu pedido" onVolver={() => irA(null)} />
        <div className="flex-1 px-4 flex flex-col gap-3">
          <div>
            {items.map((i) => (
              <ItemCarrito key={i.id} item={i} />
            ))}
          </div>
          <button type="button" onClick={() => irA(null)} className="self-start text-naranja text-sm font-semibold py-1">
            + Agregar algo más
          </button>

          {preciosNuevos > 0 && (
            <p className="p-3 rounded-xl bg-alerta/15 text-alerta text-sm">
              Actualizamos {preciosNuevos === 1 ? "un precio" : "los precios"} de tu pedido con los de ahora.
            </p>
          )}

          <Pregunta>¿Dónde lo comés?</Pregunta>
          <div role="radiogroup" aria-label="Dónde lo comés" className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-carbon border border-linea">
            {MODOS.map((m) => (
              <button
                key={m.id}
                type="button"
                role="radio"
                aria-checked={modo === m.id}
                onClick={() => {
                  setModo(m.id);
                  setErrores({});
                }}
                className={`text-center px-1 py-2.5 rounded-lg font-semibold text-[13px] leading-tight ${
                  modo === m.id ? "bg-naranja text-white" : "text-tenue"
                }`}
              >
                {m.nombre}
                <small className={`block font-normal text-[10.5px] mt-0.5 ${modo === m.id ? "text-white/85" : ""}`}>{m.bajada}</small>
              </button>
            ))}
          </div>

          {modo === "comer_adentro" && (
            <>
              <Campo etiqueta="¿Dónde estás?" id="ubicacion" error={errores.ubicacion}>
                <input
                  id="ubicacion"
                  className={claseInput}
                  placeholder="Ej: frente a la cancha 3"
                  maxLength={120}
                  autoComplete="off"
                  value={ubicacion}
                  aria-invalid={!!errores.ubicacion}
                  onChange={(e) => setUbicacion(e.target.value)}
                />
              </Campo>
              <div className="flex gap-2 flex-wrap">
                {CANCHAS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => {
                      setUbicacion(c);
                      setErrores({});
                    }}
                    className={`px-3.5 py-1.5 rounded-full border text-[13px] ${
                      ubicacion.trim().toLowerCase() === c.toLowerCase()
                        ? "bg-naranja border-naranja text-white font-semibold"
                        : "border-linea text-tenue"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <p className="text-tenue text-xs">Escribilo corto, como se lo dirías a un amigo. Los botones lo completan solos.</p>
            </>
          )}

          {modo === "take_away" && (
            <p className="text-tenue text-sm">Te avisamos acá cuando esté listo y lo retirás por la cantina.</p>
          )}

          {modo === "delivery" && (
            <div className="p-4 rounded-xl bg-carbon border border-linea grid gap-3">
              <p className="text-sm">
                El delivery lo hacemos por <b>PedidosYa</b>. Tocá el botón y pedí desde la tienda de BRUTO en la app.
              </p>
              {linkDelivery ? (
                <a
                  href={linkDelivery}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-center rounded-xl py-3 font-bold text-sm bg-[#FA0050] text-white"
                >
                  PEDIR POR PEDIDOSYA
                </a>
              ) : (
                <p className="text-tenue text-xs">Muy pronto vas a poder pedir delivery. Por ahora podés pedir take away y retirarlo.</p>
              )}
            </div>
          )}

          {modo !== "delivery" && <Total total={total} />}

          {modo !== "delivery" && cerrada && (
            <p role="alert" className="p-3 rounded-xl bg-alerta/15 text-alerta text-sm">
              {estadoTienda.mensaje || "Ahora no estamos tomando pedidos"} Tu pedido queda guardado acá.
            </p>
          )}
          {modo !== "delivery" && !cerrada && conProblema.length > 0 && (
            <p role="alert" className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm">
              Hay {conProblema.length === 1 ? "algo" : "cosas"} en tu pedido que hoy no tenemos. Sacalo para seguir.
            </p>
          )}
        </div>

        {modo !== "delivery" && (
          <BotonFijo onClick={continuar} disabled={cerrada || conProblema.length > 0}>
            {cerrada ? textoCerrada : "CONTINUAR"}
          </BotonFijo>
        )}
      </div>
    );
  }

  // ---------- paso 2: tus datos + cómo pagás ----------
  const efectivoBajada = modo === "comer_adentro" ? "Le pagás al que te lo lleva" : "Pagás al retirar en la cantina";
  return (
    <div className="min-h-dvh flex flex-col">
      <Volver titulo="Tus datos" onVolver={() => irA("pedido")} />
      <div className="flex-1 px-4 flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-2">
          <Campo etiqueta="Nombre" id="nombre" error={errores.nombre}>
            <input id="nombre" className={claseInput} autoComplete="given-name" maxLength={60} value={nombre} aria-invalid={!!errores.nombre} onChange={(e) => setNombre(e.target.value)} />
          </Campo>
          <Campo etiqueta="Apellido" id="apellido" error={errores.apellido}>
            <input id="apellido" className={claseInput} autoComplete="family-name" maxLength={60} value={apellido} aria-invalid={!!errores.apellido} onChange={(e) => setApellido(e.target.value)} />
          </Campo>
        </div>
        <Campo etiqueta="Teléfono" id="telefono" error={errores.telefono} ayuda="Lo usamos solo si no te encontramos.">
          <input
            id="telefono"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            className={`${claseInput} num`}
            placeholder="261 555 0142"
            maxLength={25}
            value={telefono}
            aria-invalid={!!errores.telefono}
            onChange={(e) => setTelefono(e.target.value)}
          />
        </Campo>

        <Pregunta>¿Cómo pagás?</Pregunta>
        <div role="radiogroup" aria-label="Cómo pagás" className="grid gap-2">
          <OpcionPago
            on={metodo === "mercadopago"}
            onElegir={() => setMetodo("mercadopago")}
            logo="MP"
            colorLogo="bg-mp text-white"
            titulo="Mercado Pago"
            bajada="Tarjeta, dinero en cuenta o QR"
          />
          <OpcionPago
            on={metodo === "efectivo"}
            onElegir={() => setMetodo("efectivo")}
            logo="$"
            colorLogo="bg-gris"
            titulo="Efectivo"
            bajada={efectivoBajada}
          />
        </div>

        <Total total={total} />

        {cerrada && (
          <p role="alert" className="p-3 rounded-xl bg-alerta/15 text-alerta text-sm">
            {estadoTienda.mensaje || "Ahora no estamos tomando pedidos"}
          </p>
        )}
        {errorEnvio && (
          <div role="alert" className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm grid gap-2">
            <p>{errorEnvio}</p>
            {conProblema.length > 0 && (
              <button type="button" onClick={() => irA("pedido")} className="justify-self-start font-semibold underline underline-offset-2">
                Revisar mi pedido
              </button>
            )}
          </div>
        )}
      </div>

      <BotonFijo mp={metodo === "mercadopago" && !cerrada} onClick={confirmar} disabled={enviando || cerrada}>
        {cerrada
          ? textoCerrada
          : enviando
          ? metodo === "mercadopago"
            ? "YENDO A MERCADO PAGO..."
            : "MANDANDO TU PEDIDO..."
          : metodo === "mercadopago"
            ? "PAGAR CON MERCADO PAGO"
            : `CONFIRMAR PEDIDO · ${precio(total)}`}
      </BotonFijo>
    </div>
  );
}
