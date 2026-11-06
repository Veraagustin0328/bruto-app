import { useEffect, useMemo, useRef, useState } from "react";
import { carta as api } from "../../api";
import llama from "../../assets/llama.png";
import { Campo, claseInput } from "../../componentes/Controles";
import { leerPrecio, precio } from "../../lib/formato";
import { Boton, Confirmar, Interruptor } from "../comunes";

// Crear o editar un producto con sus grupos de opciones y su foto.
// Todo se arma acá y se guarda junto con "Guardar": el editor compara con lo
// que había y manda solo lo que cambió (crear, cambiar o borrar cada cosa)

const MAX_FOTO = 5 * 1024 * 1024;
let siguienteClave = 1;
const clave = () => `n${siguienteClave++}`;

function aFormulario(p, categoriaId) {
  return {
    nombre: p?.nombre || "",
    categoria_id: p?.categoria_id || categoriaId,
    descripcion: p?.descripcion || "",
    precio: p ? String(Number(p.precio)) : "",
    etiqueta: p?.etiqueta || "",
    visible: p?.visible ?? true,
    disponible: p?.disponible ?? true,
    grupos: (p?.grupos || []).map((g) => ({
      clave: `g${g.id}`,
      id: g.id,
      nombre: g.nombre,
      tipo: g.tipo,
      obligatorio: g.obligatorio,
      max_selecciones: g.max_selecciones == null ? "" : String(g.max_selecciones),
      opciones: g.opciones.map((o) => ({
        clave: `o${o.id}`,
        id: o.id,
        nombre: o.nombre,
        precio_extra: String(Number(o.precio_extra)),
        cantidad_max: o.cantidad_max == null ? "" : String(o.cantidad_max),
        disponible: o.disponible,
      })),
    })),
  };
}

// Lo que hay que mandar de cada cosa, ya validado. Tira Error con el mensaje para Renzo
function limpiarProducto(f) {
  const nombre = f.nombre.trim();
  if (nombre.length < 2) throw new Error("Poné el nombre del producto");
  const p = leerPrecio(f.precio);
  if (!Number.isFinite(p)) throw new Error("Revisá el precio (ej: 13500)");
  return {
    nombre,
    categoria_id: Number(f.categoria_id),
    descripcion: f.descripcion.trim() || null,
    precio: p,
    etiqueta: f.etiqueta.trim() || null,
    visible: f.visible,
    disponible: f.disponible,
  };
}

function limpiarGrupo(g) {
  const nombre = g.nombre.trim();
  if (nombre.length < 2) throw new Error("Cada grupo de opciones necesita un nombre (ej: Tamaño)");
  const max = g.max_selecciones.trim();
  if (max && !/^[1-9]\d*$/.test(max)) throw new Error(`En ${nombre}, el tope de opciones tiene que ser un número (o vacío)`);
  return { nombre, tipo: g.tipo, obligatorio: g.obligatorio, max_selecciones: max ? Number(max) : null };
}

function limpiarOpcion(o, grupo) {
  const nombre = o.nombre.trim();
  if (!nombre) throw new Error(`Hay una opción sin nombre en ${grupo.nombre || "un grupo"}`);
  const extra = leerPrecio(o.precio_extra || "0");
  if (!Number.isFinite(extra)) throw new Error(`Revisá el precio de ${nombre}`);
  const cant = o.cantidad_max.trim();
  if (grupo.tipo === "multiple" && cant && !/^[1-9]\d*$/.test(cant)) throw new Error(`En ${nombre}, la cantidad máxima tiene que ser un número (o vacío = sin tope)`);
  return {
    nombre,
    precio_extra: extra,
    // En los de elegir una, cada opción va una sola vez
    cantidad_max: grupo.tipo === "unica" ? 1 : cant ? Number(cant) : null,
    disponible: o.disponible,
  };
}

// Solo los campos que cambiaron
function diferencias(nuevo, viejo) {
  const d = {};
  for (const k of Object.keys(nuevo)) {
    const a = nuevo[k];
    const b = viejo?.[k];
    const igual = typeof a === "number" && b != null ? a === Number(b) : a === b;
    if (!igual) d[k] = a;
  }
  return d;
}

function FotoEditable({ actual, archivo, sacar, onElegir, onSacar, error }) {
  const input = useRef(null);
  const vista = useMemo(() => (archivo ? URL.createObjectURL(archivo) : null), [archivo]);
  useEffect(() => () => vista && URL.revokeObjectURL(vista), [vista]);
  const src = vista || (!sacar && actual) || null;

  return (
    <div className="grid grid-cols-[112px_1fr] gap-3 items-center">
      <div className="w-28 h-28 rounded-xl overflow-hidden bg-gradient-to-br from-gris to-negro grid place-items-center border border-gris">
        {src ? <img src={src} alt="Cómo queda la foto" className="w-full h-full object-cover" /> : <img src={llama} alt="" className="w-10 opacity-30" />}
      </div>
      <div className="grid gap-2 justify-items-start">
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            onElegir(e.target.files?.[0] || null);
            e.target.value = "";
          }}
        />
        <div className="flex gap-2 flex-wrap">
          <Boton secundario onClick={() => input.current?.click()}>
            {src ? "Cambiar foto" : "Subir foto"}
          </Boton>
          {src && (
            <Boton peligro onClick={onSacar}>
              Sacar foto
            </Boton>
          )}
        </div>
        <p className="text-tenue text-xs">
          {archivo ? "Así se va a ver. Se sube al tocar Guardar." : "jpg, png o webp de hasta 5 MB. La achicamos sola."}
        </p>
        {error && <p className="text-naranja text-xs">{error}</p>}
      </div>
    </div>
  );
}

function EditorGrupo({ g, onCambiar, onBorrar }) {
  const [borrando, setBorrando] = useState(false);
  const set = (campo, valor) => onCambiar({ ...g, [campo]: valor });
  const setOpcion = (i, cambios) => set("opciones", g.opciones.map((o, j) => (j === i ? { ...o, ...cambios } : o)));

  return (
    <fieldset className="rounded-xl border border-gris p-3 grid gap-3">
      <legend className="sr-only">Grupo {g.nombre}</legend>
      <div className="grid sm:grid-cols-[1fr_auto] gap-2 items-end">
        <Campo etiqueta="Nombre del grupo" id={`g-${g.clave}`}>
          <input id={`g-${g.clave}`} className={claseInput} placeholder="Ej: Tamaño" maxLength={80} value={g.nombre} onChange={(e) => set("nombre", e.target.value)} />
        </Campo>
        <div className="flex rounded-xl bg-carbon border border-linea p-1 gap-1" role="radiogroup" aria-label="Cómo se elige">
          {[
            ["unica", "Elige una"],
            ["multiple", "Elige varias"],
          ].map(([v, t]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={g.tipo === v}
              onClick={() => set("tipo", v)}
              className={`px-3 py-1.5 rounded-lg text-[13px] font-semibold ${g.tipo === v ? "bg-naranja text-white" : "text-tenue"}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <Interruptor prendido={g.obligatorio} onCambiar={(v) => set("obligatorio", v)} etiqueta="Obligatorio" />
          Obligatorio
        </label>
        {g.tipo === "multiple" && (
          <label className="flex items-center gap-2">
            Hasta
            <input
              className={`${claseInput} w-16 py-1.5 num`}
              inputMode="numeric"
              placeholder="—"
              value={g.max_selecciones}
              onChange={(e) => set("max_selecciones", e.target.value.replace(/\D/g, ""))}
              aria-label="Tope de opciones distintas"
            />
            opciones distintas <small className="text-tenue">(vacío = sin tope)</small>
          </label>
        )}
      </div>

      <div className="grid gap-2">
        <div className="hidden sm:grid grid-cols-[1fr_110px_90px_auto_auto] gap-2 text-[11px] text-tenue px-1">
          <span>Opción</span>
          <span>{g.tipo === "unica" ? "Suma al precio" : "Precio extra"}</span>
          <span>{g.tipo === "multiple" ? "Cant. máx." : ""}</span>
          <span>Hay</span>
          <span />
        </div>
        {g.opciones.map((o, i) => (
          <div key={o.clave} className="grid grid-cols-[1fr_auto] sm:grid-cols-[1fr_110px_90px_auto_auto] gap-2 items-center">
            <input className={`${claseInput} py-2`} placeholder="Ej: Doble" maxLength={80} value={o.nombre} onChange={(e) => setOpcion(i, { nombre: e.target.value })} aria-label="Nombre de la opción" />
            <button type="button" onClick={() => set("opciones", g.opciones.filter((_, j) => j !== i))} className="sm:order-last w-9 h-9 rounded-lg bg-naranja/15 text-naranja" aria-label={`Sacar ${o.nombre || "opción"}`}>
              ✕
            </button>
            <div className="col-span-2 sm:col-span-1 grid grid-cols-[1fr_1fr_auto] sm:contents gap-2 items-center">
              <span className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-tenue">$</span>
                <input className={`${claseInput} py-2 pl-7 num`} inputMode="decimal" value={o.precio_extra} onChange={(e) => setOpcion(i, { precio_extra: e.target.value })} aria-label="Precio extra" />
              </span>
              {g.tipo === "multiple" ? (
                <input className={`${claseInput} py-2 num`} inputMode="numeric" placeholder="sin tope" value={o.cantidad_max} onChange={(e) => setOpcion(i, { cantidad_max: e.target.value.replace(/\D/g, "") })} aria-label="Cantidad máxima" />
              ) : (
                <span className="hidden sm:block" />
              )}
              <Interruptor prendido={o.disponible} onCambiar={(v) => setOpcion(i, { disponible: v })} etiqueta={`${o.nombre || "Opción"} disponible`} />
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() => set("opciones", [...g.opciones, { clave: clave(), nombre: "", precio_extra: "0", cantidad_max: g.tipo === "multiple" ? "" : "1", disponible: true }])}
          className="justify-self-start text-naranja text-sm font-semibold py-1"
        >
          + Agregar opción
        </button>
      </div>

      {borrando ? (
        <Confirmar texto={`¿Borrar el grupo ${g.nombre || "sin nombre"} con sus opciones?`} si="Sí, borrar" onSi={onBorrar} onNo={() => setBorrando(false)} />
      ) : (
        <button type="button" onClick={() => setBorrando(true)} className="justify-self-end text-tenue text-xs underline underline-offset-2">
          Borrar este grupo
        </button>
      )}
    </fieldset>
  );
}

export default function EditorProducto({ producto, categoriaId, categorias, onCerrar, onGuardado, avisar }) {
  const [original, setOriginal] = useState(producto);
  const [f, setF] = useState(() => aFormulario(producto, categoriaId));
  const [archivo, setArchivo] = useState(null);
  const [sacarFoto, setSacarFoto] = useState(false);
  const [errorFoto, setErrorFoto] = useState(null);
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const nuevo = !original;

  // Escape cierra, y la página de atrás no scrollea
  useEffect(() => {
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const alTeclear = (e) => e.key === "Escape" && !guardando && onCerrar();
    window.addEventListener("keydown", alTeclear);
    return () => {
      document.body.style.overflow = antes;
      window.removeEventListener("keydown", alTeclear);
    };
  }, [onCerrar, guardando]);

  const set = (campo, valor) => setF((x) => ({ ...x, [campo]: valor }));

  function elegirFoto(a) {
    setErrorFoto(null);
    if (!a) return;
    if (a.size > MAX_FOTO) {
      setErrorFoto("La foto pesa más de 5 MB. Probá con una más chica.");
      return;
    }
    setArchivo(a);
    setSacarFoto(false);
  }

  async function guardar() {
    setError(null);
    let datos;
    let grupos;
    try {
      datos = limpiarProducto(f);
      grupos = f.grupos.map((g) => ({ g, limpio: limpiarGrupo(g), opciones: g.opciones.map((o) => ({ o, limpio: limpiarOpcion(o, g) })) }));
    } catch (e) {
      setError(e.message);
      return;
    }

    setGuardando(true);
    let id = original?.id;
    try {
      // 1. el producto
      if (!id) {
        id = (await api.crearProducto(datos)).id;
      } else {
        const cambios = diferencias(datos, original);
        if (Object.keys(cambios).length) await api.editarProducto(id, cambios);
      }

      // 2. grupos y opciones: borro lo que sacó, creo lo nuevo, cambio lo cambiado
      const viejos = new Map((original?.grupos || []).map((g) => [g.id, g]));
      const quedan = new Set(f.grupos.filter((g) => g.id).map((g) => g.id));
      for (const g of viejos.values()) if (!quedan.has(g.id)) await api.borrarGrupo(g.id);

      for (const { g, limpio, opciones } of grupos) {
        if (!g.id) {
          const creado = await api.crearGrupo(id, limpio);
          for (const { limpio: op } of opciones) await api.crearOpcion(creado.id, op);
          continue;
        }
        const viejo = viejos.get(g.id);
        const cambios = diferencias(limpio, viejo);
        if (Object.keys(cambios).length) await api.editarGrupo(g.id, cambios);
        const opsViejas = new Map(viejo.opciones.map((o) => [o.id, o]));
        const opsQuedan = new Set(g.opciones.filter((o) => o.id).map((o) => o.id));
        for (const o of opsViejas.values()) if (!opsQuedan.has(o.id)) await api.borrarOpcion(o.id);
        for (const { o, limpio: op } of opciones) {
          if (!o.id) await api.crearOpcion(g.id, op);
          else {
            const c = diferencias(op, opsViejas.get(o.id));
            if (Object.keys(c).length) await api.editarOpcion(o.id, c);
          }
        }
      }

      // 3. la foto
      if (archivo) await api.subirFoto(id, archivo);
      else if (sacarFoto && original?.imagen_url) await api.borrarFoto(id);

      avisar(nuevo ? `${datos.nombre} agregado a la carta` : `${datos.nombre} guardado`);
      onGuardado();
      onCerrar();
    } catch (e) {
      // Se pudo haber guardado una parte: vuelvo a leer el producto como quedó
      setError(`${e.message}. Lo que ves abajo es lo que quedó guardado.`);
      if (id) {
        try {
          const lista = await api.ver();
          const p = lista.flatMap((c) => c.productos).find((x) => x.id === id);
          if (p) {
            setOriginal(p);
            setF(aFormulario(p, p.categoria_id));
            setArchivo(null);
            setSacarFoto(false);
          }
        } catch {
          // sin conexión: queda como estaba en pantalla
        }
      }
      onGuardado();
    } finally {
      setGuardando(false);
    }
  }

  async function borrar() {
    setGuardando(true);
    setError(null);
    try {
      await api.borrarProducto(original.id);
      avisar(`${original.nombre} borrado de la carta`);
      onGuardado();
      onCerrar();
    } catch (e) {
      setError(e.message);
      setGuardando(false);
    }
  }

  const precioBase = leerPrecio(f.precio);

  return (
    <div className="fixed inset-0 z-50 flex items-stretch md:items-center justify-center" role="dialog" aria-modal="true" aria-label={nuevo ? "Producto nuevo" : `Editar ${original.nombre}`}>
      <button type="button" aria-label="Cerrar" onClick={() => !guardando && onCerrar()} className="absolute inset-0 bg-black/70" />
      <div className="relative w-full md:max-w-2xl md:max-h-[92dvh] flex flex-col bg-negro md:rounded-2xl md:border md:border-gris overflow-hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-gris">
          <h2 className="text-[26px] truncate">{nuevo ? "Producto nuevo" : original.nombre}</h2>
          <button type="button" onClick={onCerrar} disabled={guardando} className="w-9 h-9 rounded-full bg-gris grid place-items-center" aria-label="Cerrar">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 grid gap-4 content-start">
          <FotoEditable
            actual={original?.imagen_url}
            archivo={archivo}
            sacar={sacarFoto}
            error={errorFoto}
            onElegir={elegirFoto}
            onSacar={() => {
              setArchivo(null);
              setSacarFoto(true);
            }}
          />

          <div className="grid sm:grid-cols-2 gap-3">
            <Campo etiqueta="Nombre" id="ed-nombre">
              <input id="ed-nombre" className={claseInput} maxLength={120} value={f.nombre} onChange={(e) => set("nombre", e.target.value)} />
            </Campo>
            <Campo etiqueta="Categoría" id="ed-cat">
              <select id="ed-cat" className={claseInput} value={f.categoria_id} onChange={(e) => set("categoria_id", Number(e.target.value))}>
                {categorias.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Precio" id="ed-precio" ayuda={Number.isFinite(precioBase) ? precio(precioBase) : "Ej: 13500"}>
              <input id="ed-precio" className={`${claseInput} num`} inputMode="decimal" value={f.precio} onChange={(e) => set("precio", e.target.value)} />
            </Campo>
            <Campo etiqueta="Etiqueta (opcional)" id="ed-etiqueta" ayuda="Ej: Recomendada, Nuevo, Próximamente">
              <input id="ed-etiqueta" className={claseInput} maxLength={40} value={f.etiqueta} onChange={(e) => set("etiqueta", e.target.value)} />
            </Campo>
          </div>
          <Campo etiqueta="Descripción" id="ed-desc">
            <textarea id="ed-desc" rows={2} className={`${claseInput} resize-y`} maxLength={1000} value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)} />
          </Campo>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <label className="flex items-center gap-2">
              <Interruptor prendido={f.visible} onCambiar={(v) => set("visible", v)} etiqueta="Se ve en la carta" />
              Se ve en la carta
            </label>
            <label className="flex items-center gap-2">
              <Interruptor prendido={f.disponible} onCambiar={(v) => set("disponible", v)} etiqueta="Se puede pedir" />
              Se puede pedir <small className="text-tenue">(apagado = sin stock o próximamente)</small>
            </label>
          </div>

          <div className="grid gap-3">
            <h3 className="text-[22px]">Opciones</h3>
            {f.grupos.length === 0 && <p className="text-tenue text-sm">Sin opciones. Ej: Tamaño (Simple / Doble) o Agregados.</p>}
            {f.grupos.map((g, i) => (
              <EditorGrupo
                key={g.clave}
                g={g}
                onCambiar={(ng) => set("grupos", f.grupos.map((x, j) => (j === i ? ng : x)))}
                onBorrar={() => set("grupos", f.grupos.filter((_, j) => j !== i))}
              />
            ))}
            <button
              type="button"
              onClick={() =>
                set("grupos", [
                  ...f.grupos,
                  { clave: clave(), nombre: "", tipo: "unica", obligatorio: true, max_selecciones: "", opciones: [{ clave: clave(), nombre: "", precio_extra: "0", cantidad_max: "1", disponible: true }] },
                ])
              }
              className="justify-self-start px-3 py-2 rounded-lg border border-dashed border-linea text-sm font-semibold text-tenue hover:text-texto"
            >
              + Agregar grupo de opciones
            </button>
          </div>

          {!nuevo && (
            <div className="pt-2 border-t border-gris">
              {borrando ? (
                <Confirmar
                  texto={`¿Borrar ${original.nombre} de la carta? Los pedidos que ya se hicieron no cambian. Si es por un tiempo, mejor apagá "Se ve en la carta".`}
                  si="Sí, borrar"
                  ocupado={guardando}
                  onSi={borrar}
                  onNo={() => setBorrando(false)}
                />
              ) : (
                <Boton peligro onClick={() => setBorrando(true)}>
                  Borrar producto
                </Boton>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-gris px-4 py-3 grid gap-2 pb-[max(12px,env(safe-area-inset-bottom))]">
          {error && (
            <p role="alert" className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Boton secundario grande disabled={guardando} onClick={onCerrar}>
              Cancelar
            </Boton>
            <Boton grande disabled={guardando} onClick={guardar}>
              {guardando ? "Guardando..." : nuevo ? "Crear producto" : "Guardar"}
            </Boton>
          </div>
        </div>
      </div>
    </div>
  );
}
