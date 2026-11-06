import { useCallback, useEffect, useRef, useState } from "react";
import { carta as api } from "../../api";
import { claseInput } from "../../componentes/Controles";
import { leerPrecio, precio } from "../../lib/formato";
import { AvisoConexion, Avisos, Boton, Confirmar, EnVivo, Esqueleto, Interruptor, Titulo, useAncho, useAvisos } from "../comunes";
import Marco from "../Marco";
import useEventosPanel from "../useEventosPanel";
import Aumento from "./Aumento";
import EditorProducto from "./EditorProducto";

// Carta y precios (parte 4 de la maqueta). El admin ve todo; la cantina solo
// prende y apaga productos y opciones (la bondiola sin stock)

// Mueve el elemento i un lugar para arriba (-1) o para abajo (+1)
function mover(lista, i, dir) {
  const sig = [...lista];
  const j = i + dir;
  if (j < 0 || j >= sig.length) return lista;
  [sig[i], sig[j]] = [sig[j], sig[i]];
  return sig;
}

function Flechas({ etiqueta, primero, ultimo, onMover, disabled }) {
  const clase = "w-7 h-6 rounded-md bg-gris text-tenue text-[11px] leading-none grid place-items-center disabled:opacity-30 hover:text-texto";
  return (
    <span className="flex flex-col gap-0.5 flex-none">
      <button type="button" className={clase} disabled={disabled || primero} onClick={() => onMover(-1)} aria-label={`Subir ${etiqueta}`}>
        ▲
      </button>
      <button type="button" className={clase} disabled={disabled || ultimo} onClick={() => onMover(1)} aria-label={`Bajar ${etiqueta}`}>
        ▼
      </button>
    </span>
  );
}

// Tocar el precio lo deja editar ahí mismo. Enter o ✓ guarda, Escape o ✕ cancela
function PrecioEditable({ producto, onGuardado, avisar }) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);

  function abrir() {
    setValor(String(Number(producto.precio)));
    setError(null);
    setEditando(true);
  }

  async function guardar() {
    const n = leerPrecio(valor);
    if (!Number.isFinite(n)) {
      setError("Poné un número, ej: 13500");
      return;
    }
    if (n === Number(producto.precio)) {
      setEditando(false);
      return;
    }
    setGuardando(true);
    try {
      onGuardado(await api.editarProducto(producto.id, { precio: n }));
      avisar(`${producto.nombre}: ${precio(n)}`);
      setEditando(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  }

  if (!editando) {
    return (
      <button
        type="button"
        onClick={abrir}
        className="num font-semibold text-[13.5px] px-2 py-1 rounded-md hover:bg-gris border border-transparent hover:border-linea"
        aria-label={`Cambiar el precio de ${producto.nombre}, ahora ${precio(producto.precio)}`}
      >
        {precio(producto.precio)}
      </button>
    );
  }
  return (
    <span className="flex flex-col items-end gap-1">
      <span className="flex items-center gap-1">
        <span className="relative">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-tenue text-sm">$</span>
          <input
            autoFocus
            className={`${claseInput} w-28 py-1.5 pl-5 text-sm num`}
            inputMode="decimal"
            value={valor}
            disabled={guardando}
            onChange={(e) => setValor(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") guardar();
              if (e.key === "Escape") setEditando(false);
            }}
            aria-label={`Precio nuevo de ${producto.nombre}`}
          />
        </span>
        <button type="button" onClick={guardar} disabled={guardando} className="w-8 h-8 rounded-lg bg-naranja text-white font-bold disabled:opacity-50" aria-label="Guardar precio">
          {guardando ? "…" : "✓"}
        </button>
        <button type="button" onClick={() => setEditando(false)} disabled={guardando} className="w-8 h-8 rounded-lg bg-gris" aria-label="Cancelar">
          ✕
        </button>
      </span>
      {error && <small className="text-naranja text-xs">{error}</small>}
    </span>
  );
}

function FilaProducto({ p, esAdmin, primero, ultimo, ordenando, onMover, onEditar, onCambio, avisar }) {
  const [verOpciones, setVerOpciones] = useState(false);
  const opciones = p.grupos.flatMap((g) => g.opciones.map((o) => ({ ...o, grupo: g.nombre })));

  // Optimista: se ve al toque y si falla vuelve como estaba
  async function disponible(valor) {
    onCambio({ ...p, disponible: valor });
    try {
      onCambio(await api.disponibleProducto(p.id, valor));
      avisar(valor ? `${p.nombre}: hay de nuevo` : `${p.nombre}: sin stock`);
    } catch (e) {
      onCambio(p);
      avisar(e.message, "error");
    }
  }

  async function opcionDisponible(o, valor) {
    const conCambio = (v) => ({ ...p, grupos: p.grupos.map((g) => ({ ...g, opciones: g.opciones.map((x) => (x.id === o.id ? { ...x, disponible: v } : x)) })) });
    onCambio(conCambio(valor));
    try {
      await api.disponibleOpcion(o.id, valor);
      avisar(valor ? `${o.nombre}: hay de nuevo` : `${o.nombre}: sin stock`);
    } catch (e) {
      onCambio(p);
      avisar(e.message, "error");
    }
  }

  const apagado = !p.disponible || !p.visible;
  return (
    <li className={`rounded-xl bg-carbon ${apagado ? "text-tenue" : ""}`}>
      <div className="flex items-center gap-2 px-2.5 py-2">
        {esAdmin && <Flechas etiqueta={p.nombre} primero={primero} ultimo={ultimo} disabled={ordenando} onMover={onMover} />}
        <div className="flex-1 min-w-0 text-[13.5px]">
          <span className="font-medium">{p.nombre}</span>
          {!p.disponible && <span> · {p.etiqueta && /pr[oó]ximamente/i.test(p.etiqueta) ? "próximamente" : "sin stock"}</span>}
          {!p.visible && <span className="ml-1.5 text-[10px] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded bg-gris">Oculto</span>}
          {opciones.length > 0 && (
            <button type="button" onClick={() => setVerOpciones((v) => !v)} className="block text-[11.5px] text-tenue underline-offset-2 hover:underline" aria-expanded={verOpciones}>
              {verOpciones ? "▾" : "▸"} {opciones.length} opciones
              {opciones.some((o) => !o.disponible) && <span className="text-alerta"> · alguna sin stock</span>}
            </button>
          )}
        </div>
        {esAdmin ? (
          <PrecioEditable producto={p} onGuardado={onCambio} avisar={avisar} />
        ) : (
          <span className="num text-[13.5px] font-semibold px-1">{precio(p.precio)}</span>
        )}
        <Interruptor prendido={p.disponible} onCambiar={disponible} etiqueta={`${p.nombre} disponible`} />
        {esAdmin && (
          <button type="button" onClick={onEditar} className="w-8 h-8 flex-none rounded-lg bg-gris text-tenue hover:text-texto" aria-label={`Editar ${p.nombre}`} title="Editar">
            ✎
          </button>
        )}
      </div>
      {verOpciones && (
        <ul className="px-3 pb-2.5 grid gap-1">
          {opciones.map((o) => (
            <li key={o.id} className="flex items-center justify-between gap-2 pl-6 text-[12.5px]">
              <span className={o.disponible ? "" : "text-tenue"}>
                <small className="text-tenue">{o.grupo} · </small>
                {o.nombre}
                {Number(o.precio_extra) > 0 && <small className="text-tenue num"> +{precio(o.precio_extra)}</small>}
              </span>
              <Interruptor prendido={o.disponible} onCambiar={(v) => opcionDisponible(o, v)} etiqueta={`${o.nombre} disponible`} />
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function CabeceraCategoria({ c, esAdmin, primero, ultimo, ordenando, onMover, onNuevoProducto, onCambio, onRecargar, avisar }) {
  const [renombrando, setRenombrando] = useState(false);
  const [nombre, setNombre] = useState(c.nombre);
  const [borrando, setBorrando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  if (!esAdmin) return <h4 className="text-[11px] tracking-[0.15em] text-tenue uppercase font-semibold mt-3 mb-0.5 px-1">{c.nombre}</h4>;

  async function guardarNombre() {
    const n = nombre.trim();
    if (n.length < 2 || n === c.nombre) {
      setRenombrando(false);
      setNombre(c.nombre);
      return;
    }
    setOcupado(true);
    try {
      const r = await api.editarCategoria(c.id, { nombre: n });
      onCambio({ ...c, nombre: r.nombre });
      setRenombrando(false);
    } catch (e) {
      avisar(e.message, "error");
    } finally {
      setOcupado(false);
    }
  }

  async function activa(valor) {
    onCambio({ ...c, activa: valor });
    try {
      await api.editarCategoria(c.id, { activa: valor });
      avisar(valor ? `${c.nombre} se ve en la tienda` : `${c.nombre} quedó oculta en la tienda`);
    } catch (e) {
      onCambio(c);
      avisar(e.message, "error");
    }
  }

  async function borrar() {
    setOcupado(true);
    try {
      await api.borrarCategoria(c.id);
      avisar(`${c.nombre} borrada`);
      onRecargar();
    } catch (e) {
      // Si tiene productos el backend dice qué hacer (409)
      avisar(e.message, "error");
      setBorrando(false);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="mt-4 mb-1 grid gap-2">
      <div className="flex items-center gap-2">
        <Flechas etiqueta={c.nombre} primero={primero} ultimo={ultimo} disabled={ordenando} onMover={onMover} />
        {renombrando ? (
          <span className="flex-1 flex gap-1">
            <input
              autoFocus
              className={`${claseInput} py-1.5 text-sm`}
              value={nombre}
              maxLength={80}
              disabled={ocupado}
              onChange={(e) => setNombre(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") guardarNombre();
                if (e.key === "Escape") {
                  setRenombrando(false);
                  setNombre(c.nombre);
                }
              }}
              aria-label="Nombre de la categoría"
            />
            <button type="button" onClick={guardarNombre} className="w-9 rounded-lg bg-naranja text-white font-bold" aria-label="Guardar nombre">
              ✓
            </button>
          </span>
        ) : (
          <h4 className={`flex-1 text-[12px] tracking-[0.15em] uppercase font-semibold ${c.activa ? "text-tenue" : "text-tenue/60 line-through"}`}>
            <button type="button" onClick={() => setRenombrando(true)} className="uppercase tracking-[0.15em] hover:text-texto text-left" title="Cambiar nombre">
              {c.nombre}
            </button>
          </h4>
        )}
        <Interruptor prendido={c.activa} onCambiar={activa} etiqueta={`Mostrar ${c.nombre} en la tienda`} />
      </div>
      <div className="flex gap-3 pl-9 text-[12px]">
        <button type="button" onClick={onNuevoProducto} className="text-naranja font-semibold">
          + Producto
        </button>
        {!c.activa && <span className="text-tenue">Oculta en la tienda</span>}
        <button type="button" onClick={() => setBorrando(true)} className="text-tenue hover:text-texto ml-auto">
          Borrar categoría
        </button>
      </div>
      {borrando && (
        <Confirmar
          texto={c.productos.length ? `${c.nombre} tiene ${c.productos.length} productos: movelos o borralos antes, o apagala para que no se vea.` : `¿Borrar la categoría ${c.nombre}?`}
          si="Sí, borrar"
          ocupado={ocupado}
          onSi={borrar}
          onNo={() => setBorrando(false)}
        />
      )}
    </div>
  );
}

function NuevaCategoria({ onCreada, avisar }) {
  const [abierta, setAbierta] = useState(false);
  const [nombre, setNombre] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function crear() {
    const n = nombre.trim();
    if (n.length < 2) return;
    setOcupado(true);
    try {
      await api.crearCategoria({ nombre: n });
      avisar(`Categoría ${n} creada`);
      setNombre("");
      setAbierta(false);
      onCreada();
    } catch (e) {
      avisar(e.message, "error");
    } finally {
      setOcupado(false);
    }
  }

  if (!abierta) {
    return (
      <button type="button" onClick={() => setAbierta(true)} className="mt-4 w-full px-3 py-2.5 rounded-xl border border-dashed border-linea text-sm font-semibold text-tenue hover:text-texto">
        + Nueva categoría
      </button>
    );
  }
  return (
    <div className="mt-4 flex gap-2">
      <input autoFocus className={claseInput} placeholder="Ej: Bebidas" maxLength={80} value={nombre} onChange={(e) => setNombre(e.target.value)} onKeyDown={(e) => e.key === "Enter" && crear()} aria-label="Nombre de la categoría nueva" />
      <Boton grande disabled={ocupado || nombre.trim().length < 2} onClick={crear}>
        Crear
      </Boton>
      <Boton grande secundario onClick={() => setAbierta(false)}>
        ✕
      </Boton>
    </div>
  );
}

export default function CartaPrecios({ sesion }) {
  const esAdmin = sesion.usuario.rol === "admin";
  const ancho = useAncho(1024);
  const [cats, setCats] = useState(null);
  const [error, setError] = useState(null);
  const [recargando, setRecargando] = useState(false);
  const [version, setVersion] = useState(0); // sube cada vez que llega la carta de nuevo
  const [ordenando, setOrdenando] = useState(false);
  const [editor, setEditor] = useState(null); // { producto } o { categoriaId } para uno nuevo
  const [verAumento, setVerAumento] = useState(false);
  const { avisos, avisar } = useAvisos();

  const recargar = useCallback(async () => {
    setRecargando(true);
    try {
      setCats(await api.ver());
      setVersion((v) => v + 1);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setRecargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  // Si otro usuario cambia la carta (o la cantina apaga algo), se actualiza sola
  const espera = useRef(null);
  const conectado = useEventosPanel(sesion.token, {
    onEvento: (m) => {
      if (m.evento !== "carta_actualizada") return;
      clearTimeout(espera.current);
      espera.current = setTimeout(recargar, 300);
    },
    onReconecta: recargar,
  });
  useEffect(() => () => clearTimeout(espera.current), []);

  const cambiarProducto = useCallback((prod) => {
    setCats((cs) => cs?.map((c) => ({ ...c, productos: c.productos.map((p) => (p.id === prod.id ? { ...p, ...prod } : p)) })));
  }, []);
  const cambiarCategoria = useCallback((cat) => {
    setCats((cs) => cs?.map((c) => (c.id === cat.id ? { ...c, ...cat } : c)));
  }, []);

  async function moverCategoria(i, dir) {
    const nuevas = mover(cats, i, dir);
    setCats(nuevas);
    setOrdenando(true);
    try {
      await api.ordenarCategorias(nuevas.map((c) => c.id));
    } catch (e) {
      avisar(e.message, "error");
      recargar();
    } finally {
      setOrdenando(false);
    }
  }

  async function moverProducto(cat, i, dir) {
    const productos = mover(cat.productos, i, dir);
    cambiarCategoria({ ...cat, productos });
    setOrdenando(true);
    try {
      await api.ordenarProductos(cat.id, productos.map((p) => p.id));
    } catch (e) {
      avisar(e.message, "error");
      recargar();
    } finally {
      setOrdenando(false);
    }
  }

  const aumento = esAdmin && cats && cats.length > 0 && <Aumento categorias={cats} version={version} onAplicado={recargar} avisar={avisar} />;

  return (
    <Marco sesion={sesion} derecha={<EnVivo conectado={conectado} />}>
      <AvisoConexion conectado={conectado} error={error} onReintentar={recargar} recargando={recargando} />
      <Titulo
        bajada={
          esAdmin
            ? "Tocá un precio para cambiarlo. El interruptor prende o apaga un producto si una noche se quedan sin algo."
            : "Si se quedan sin algo, apagalo acá y en la tienda sale como que hoy no hay."
        }
      >
        {esAdmin ? "Carta y precios" : "Carta"}
      </Titulo>

      <div className="px-4 md:px-6 py-4 pb-24 lg:grid lg:grid-cols-[minmax(360px,460px)_1fr] gap-6 items-start">
        <div>
          {esAdmin && !ancho && cats && (
            <div className="mb-3">
              <Boton grande secundario className="w-full" onClick={() => setVerAumento((v) => !v)} aria-expanded={verAumento}>
                {verAumento ? "▾" : "▸"} Aumento de precios
              </Boton>
              {verAumento && <div className="mt-3">{aumento}</div>}
            </div>
          )}

          {!cats ? (
            <div className="grid gap-2">
              <Esqueleto alto="h-10" />
              <Esqueleto alto="h-10" />
              <Esqueleto alto="h-10" />
            </div>
          ) : (
            <div className="bg-negro border border-gris rounded-2xl p-3">
              {cats.length === 0 && <p className="text-tenue text-sm p-2">Todavía no hay categorías.</p>}
              {cats.map((c, i) => (
                <section key={c.id}>
                  <CabeceraCategoria
                    c={c}
                    esAdmin={esAdmin}
                    primero={i === 0}
                    ultimo={i === cats.length - 1}
                    ordenando={ordenando}
                    onMover={(dir) => moverCategoria(i, dir)}
                    onNuevoProducto={() => setEditor({ categoriaId: c.id })}
                    onCambio={cambiarCategoria}
                    onRecargar={recargar}
                    avisar={avisar}
                  />
                  <ul className="grid gap-1.5">
                    {c.productos.map((p, j) => (
                      <FilaProducto
                        key={p.id}
                        p={p}
                        esAdmin={esAdmin}
                        primero={j === 0}
                        ultimo={j === c.productos.length - 1}
                        ordenando={ordenando}
                        onMover={(dir) => moverProducto(c, j, dir)}
                        onEditar={() => setEditor({ producto: p })}
                        onCambio={cambiarProducto}
                        avisar={avisar}
                      />
                    ))}
                    {c.productos.length === 0 && <li className="text-tenue text-xs px-2 py-1">Sin productos</li>}
                  </ul>
                </section>
              ))}
              {esAdmin && <NuevaCategoria onCreada={recargar} avisar={avisar} />}
            </div>
          )}
        </div>

        {esAdmin && ancho && <div className="lg:sticky lg:top-4">{aumento}</div>}
      </div>

      {editor && cats && (
        <EditorProducto
          producto={editor.producto}
          categoriaId={editor.categoriaId}
          categorias={cats}
          onCerrar={() => setEditor(null)}
          onGuardado={recargar}
          avisar={avisar}
        />
      )}
      <Avisos avisos={avisos} />
    </Marco>
  );
}
