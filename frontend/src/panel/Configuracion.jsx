import { useCallback, useEffect, useState } from "react";
import { config as api, tienda } from "../api";
import { Campo, claseInput } from "../componentes/Controles";
import { hora } from "../lib/formato";
import { AvisoConexion, Avisos, Boton, EnVivo, Esqueleto, Interruptor, Titulo, useAvisos } from "./comunes";
import Marco from "./Marco";
import Pausa from "./Pausa";
import useEventosPanel from "./useEventosPanel";

// Configuración (solo admin): pausa, horario de cada día, mensajes y link de PedidosYa

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function Tarjeta({ titulo, bajada, children }) {
  return (
    <section className="bg-negro border border-gris rounded-2xl p-4 md:p-5 grid gap-3 content-start">
      <div>
        <h2 className="text-[24px]">{titulo}</h2>
        {bajada && <p className="text-tenue text-[13px]">{bajada}</p>}
      </div>
      {children}
    </section>
  );
}

// "Abierta hasta las 00:30", "Cerrada", "En pausa": lo mismo que ve el cliente
function EstadoAhora({ version }) {
  const [estado, setEstado] = useState(null);
  const [fallo, setFallo] = useState(false);
  useEffect(() => {
    let vivo = true;
    const traer = () =>
      tienda
        .estado()
        .then((e) => {
          if (!vivo) return;
          setEstado(e);
          setFallo(false);
        })
        .catch(() => vivo && setFallo(true));
    traer();
    const t = setInterval(traer, 30000);
    return () => {
      vivo = false;
      clearInterval(t);
    };
  }, [version]);

  if (!estado) return <p className="text-tenue text-sm">{fallo ? "No pudimos ver cómo está la tienda." : "Mirando la tienda..."}</p>;
  const [texto, color] = !estado.abierto
    ? ["Cerrada", "text-tenue"]
    : estado.pausado
      ? ["En pausa", "text-alerta"]
      : [`Abierta${estado.horario_hoy ? ` hasta las ${hora(estado.horario_hoy.cierra)}` : ""}`, "text-ok"];
  return (
    <p className="text-sm">
      La tienda ahora: <b className={color}>{texto}</b>
      {estado.mensaje && <span className="block text-tenue text-xs mt-0.5">El cliente ve: “{estado.mensaje}”</span>}
    </p>
  );
}

function aMinutos(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function Horarios({ inicial, onGuardado, avisar }) {
  const [dias, setDias] = useState(() =>
    DIAS.map((_, i) => {
      const h = inicial.find((x) => x.dia_semana === i);
      return { dia_semana: i, abierto: h ? h.abierto : false, abre: h ? hora(h.abre) : "18:00", cierra: h ? hora(h.cierra) : "00:30" };
    }),
  );
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const cambiar = (i, cambios) => setDias((ds) => ds.map((d, j) => (j === i ? { ...d, ...cambios } : d)));

  async function guardar() {
    const malo = dias.find((d) => !d.abre || !d.cierra || d.abre === d.cierra);
    if (malo) {
      setError(`El ${DIAS[malo.dia_semana].toLowerCase()} tiene que abrir y cerrar a horas distintas`);
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      onGuardado(await api.horarios(dias));
      avisar("Horario guardado");
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <>
      <ul className="grid gap-2">
        {dias.map((d, i) => {
          const cruza = d.abierto && d.abre && d.cierra && aMinutos(d.cierra) < aMinutos(d.abre);
          return (
            <li key={i} className={`rounded-xl bg-carbon px-3 py-2.5 grid grid-cols-[1fr_auto] sm:grid-cols-[100px_auto_1fr] gap-x-3 gap-y-2 items-center ${d.abierto ? "" : "text-tenue"}`}>
              <b className="font-semibold text-sm">{DIAS[i]}</b>
              <Interruptor prendido={d.abierto} onCambiar={(v) => cambiar(i, { abierto: v })} etiqueta={`Abre el ${DIAS[i].toLowerCase()}`} />
              {d.abierto ? (
                <span className="col-span-2 sm:col-span-1 flex items-center gap-2">
                  <input type="time" className={`${claseInput} sm:max-w-[7.5rem] py-1.5 num`} value={d.abre} onChange={(e) => cambiar(i, { abre: e.target.value })} aria-label={`${DIAS[i]}: abre`} />
                  <span className="text-tenue text-sm">a</span>
                  <input type="time" className={`${claseInput} sm:max-w-[7.5rem] py-1.5 num`} value={d.cierra} onChange={(e) => cambiar(i, { cierra: e.target.value })} aria-label={`${DIAS[i]}: cierra`} />
                </span>
              ) : (
                <span className="col-span-2 sm:col-span-1 text-sm">No abre</span>
              )}
              {cruza && (
                <small className="col-span-2 sm:col-span-1 sm:col-start-3 text-tenue text-xs">
                  Pasa la medianoche: cierra el {DIAS[(i + 1) % 7].toLowerCase()} a las {d.cierra}
                </small>
              )}
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setDias((ds) => ds.map((d) => ({ ...d, abierto: ds[0].abierto, abre: ds[0].abre, cierra: ds[0].cierra })))}
          className="text-tenue text-[13px] underline underline-offset-2"
        >
          Usar el horario del lunes para todos
        </button>
        <Boton grande disabled={guardando} onClick={guardar}>
          {guardando ? "Guardando..." : "Guardar horario"}
        </Boton>
      </div>
      {error && <p className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm">{error}</p>}
    </>
  );
}

function CampoGuardable({ etiqueta, id, valor, ayuda, multilinea = false, placeholder, onGuardar }) {
  const [texto, setTexto] = useState(valor || "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => setTexto(valor || ""), [valor]);
  const cambiado = texto.trim() !== (valor || "");

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      await onGuardar(texto.trim());
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  }

  const Input = multilinea ? "textarea" : "input";
  return (
    <div className="grid gap-2">
      <Campo etiqueta={etiqueta} id={id} ayuda={ayuda} error={error}>
        <Input id={id} rows={multilinea ? 2 : undefined} className={`${claseInput} ${multilinea ? "resize-y" : ""}`} placeholder={placeholder} value={texto} onChange={(e) => setTexto(e.target.value)} />
      </Campo>
      {cambiado && (
        <div className="flex justify-end gap-2">
          <Boton secundario onClick={() => setTexto(valor || "")} disabled={guardando}>
            Deshacer
          </Boton>
          <Boton onClick={guardar} disabled={guardando}>
            {guardando ? "Guardando..." : "Guardar"}
          </Boton>
        </div>
      )}
    </div>
  );
}

export default function Configuracion({ sesion }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);
  const { avisos, avisar } = useAvisos();

  const cargar = useCallback(async () => {
    try {
      setDatos(await api.ver());
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const conectado = useEventosPanel(sesion.token, {
    onEvento: (m) => {
      if (m.evento !== "config_actualizada") return;
      setVersion((v) => v + 1);
      cargar();
    },
    onReconecta: cargar,
  });

  const guardar = (campo, textoOk) => async (valor) => {
    const r = await api.editar({ [campo]: valor || null });
    setDatos(r);
    setVersion((v) => v + 1);
    avisar(textoOk);
  };

  return (
    <Marco sesion={sesion} derecha={<EnVivo conectado={conectado} />}>
      <AvisoConexion conectado={conectado} error={error} onReintentar={cargar} />
      <Titulo bajada="Lo que cambies acá lo ve el cliente al toque en la tienda.">Configuración</Titulo>

      <div className="px-4 md:px-6 py-4 pb-24 grid lg:grid-cols-2 gap-4 items-start">
        <div className="grid gap-4">
          <Tarjeta titulo="Pedidos" bajada="La pausa también la pueden tocar los chicos de la cantina desde Pedidos.">
            <Pausa grande version={version} avisar={avisar} />
            <EstadoAhora version={version} />
          </Tarjeta>

          <Tarjeta titulo="Mensajes para el cliente">
            {!datos ? (
              <Esqueleto alto="h-28" />
            ) : (
              <>
                <CampoGuardable etiqueta="Cuando los pedidos están en pausa" id="msj-pausa" multilinea valor={datos.mensaje_pausado} onGuardar={guardar("mensaje_pausado", "Mensaje de pausa guardado")} />
                <CampoGuardable etiqueta="Cuando la cantina está cerrada" id="msj-cerrado" multilinea valor={datos.mensaje_cerrado} onGuardar={guardar("mensaje_cerrado", "Mensaje de cerrado guardado")} />
              </>
            )}
          </Tarjeta>

          <Tarjeta titulo="Delivery" bajada="El botón de Delivery de la tienda abre este link. Vacío = la tienda dice que el delivery viene pronto.">
            {!datos ? (
              <Esqueleto alto="h-16" />
            ) : (
              <>
                <CampoGuardable
                  etiqueta="Link de la tienda de BRUTO en PedidosYa"
                  id="link-pya"
                  placeholder="https://www.pedidosya.com.ar/restaurantes/mendoza/bruto..."
                  valor={datos.link_pedidosya}
                  ayuda="Tiene que empezar con https://"
                  onGuardar={guardar("link_pedidosya", "Link de PedidosYa guardado")}
                />
                {datos.link_pedidosya && (
                  <a href={datos.link_pedidosya} target="_blank" rel="noopener noreferrer" className="text-naranja text-sm font-semibold justify-self-start">
                    Probar el link ↗
                  </a>
                )}
              </>
            )}
          </Tarjeta>
        </div>

        <Tarjeta titulo="Horario" bajada="De 18:00 a 00:30 pasa la medianoche: la madrugada del martes cuenta como turno del lunes.">
          {!datos ? <Esqueleto alto="h-80" /> : <Horarios key={JSON.stringify(datos.horarios)} inicial={datos.horarios} onGuardado={setDatos} avisar={avisar} />}
        </Tarjeta>
      </div>
      <Avisos avisos={avisos} />
    </Marco>
  );
}
