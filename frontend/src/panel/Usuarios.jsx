import { useCallback, useEffect, useState } from "react";
import { usuarios as api } from "../api";
import { Campo, claseInput } from "../componentes/Controles";
import { AvisoConexion, Avisos, Boton, Confirmar, Esqueleto, Titulo, useAvisos } from "./comunes";
import Marco from "./Marco";
import { NOMBRE_ROL } from "./sesion";

// Usuarios (solo admin): crear, cambiar rol, dar de baja y de alta, y
// cambiarle la contraseña a alguien que se la olvidó

const ROLES = [
  { id: "cantina", nombre: "Cantina", que: "Pedidos, cocina, cobrar, caja del día y pausar" },
  { id: "cocina", nombre: "Cocina", que: "Solo la pantalla de comandas" },
  { id: "admin", nombre: "Admin", que: "Todo: carta, precios, caja, configuración y usuarios" },
  { id: "impresora", nombre: "Ticketera", que: "Solo para el programa de la impresora de comandas" },
];

function UsuarioFila({ u, soyYo, onCambio, avisar }) {
  const [rol, setRol] = useState(u.rol);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [clave, setClave] = useState(null); // null = cerrado; string = escribiendo
  const [bajando, setBajando] = useState(false);
  useEffect(() => setRol(u.rol), [u.rol]);

  async function cambiar(cambios, textoOk) {
    setOcupado(true);
    setError(null);
    try {
      onCambio(await api.editar(u.id, cambios));
      avisar(textoOk);
      return true;
    } catch (e) {
      // Ej: "No te podés dar de baja ni sacarte el admin a vos mismo"
      setError(e.message);
      setRol(u.rol);
      return false;
    } finally {
      setOcupado(false);
    }
  }

  async function guardarClave() {
    if ((clave || "").length < 8) {
      setError("La contraseña nueva tiene que tener al menos 8 caracteres");
      return;
    }
    if (await cambiar({ password: clave }, `Contraseña de ${u.nombre} cambiada`)) setClave(null);
  }

  return (
    <li className={`bg-negro border rounded-2xl p-3.5 grid gap-3 ${u.activo ? "border-gris" : "border-gris/60"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <b className={`block font-semibold ${u.activo ? "" : "text-tenue line-through"}`}>
            {u.nombre} {soyYo && <span className="text-naranja font-normal text-xs no-underline">(vos)</span>}
          </b>
          <small className="text-tenue break-all">{u.email}</small>
        </div>
        <span
          className={`text-[10.5px] font-bold tracking-wider uppercase px-2 py-1 rounded ${
            !u.activo ? "bg-gris text-tenue" : u.rol === "admin" ? "bg-naranja text-white" : "border border-linea text-texto"
          }`}
        >
          {u.activo ? NOMBRE_ROL[u.rol] : "Dado de baja"}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-tenue text-xs">Rol</span>
          <select
            className={`${claseInput} w-auto py-1.5 text-sm`}
            value={rol}
            disabled={ocupado}
            onChange={(e) => {
              setRol(e.target.value);
              cambiar({ rol: e.target.value }, `${u.nombre} ahora es ${NOMBRE_ROL[e.target.value]}`);
            }}
            aria-label={`Rol de ${u.nombre}`}
          >
            {ROLES.map((r) => (
              <option key={r.id} value={r.id}>
                {r.nombre}
              </option>
            ))}
          </select>
        </label>
        <div className="flex-1" />
        {clave === null && (
          <Boton secundario disabled={ocupado} onClick={() => setClave("")}>
            Cambiar contraseña
          </Boton>
        )}
        {u.activo ? (
          <Boton peligro disabled={ocupado} onClick={() => setBajando(true)}>
            Dar de baja
          </Boton>
        ) : (
          <Boton disabled={ocupado} onClick={() => cambiar({ activo: true }, `${u.nombre} está activo de nuevo`)}>
            Dar de alta
          </Boton>
        )}
      </div>

      {bajando && (
        <Confirmar
          texto={`¿Dar de baja a ${u.nombre}? No va a poder entrar más (si está adentro, lo saca al toque). Lo podés volver a dar de alta.`}
          si="Sí, dar de baja"
          ocupado={ocupado}
          onSi={async () => {
            await cambiar({ activo: false }, `${u.nombre} dado de baja`);
            setBajando(false);
          }}
          onNo={() => setBajando(false)}
        />
      )}

      {clave !== null && (
        <div className="grid gap-2 rounded-xl bg-carbon p-3">
          <Campo etiqueta={`Contraseña nueva para ${u.nombre}`} id={`clave-${u.id}`} ayuda="Al menos 8 caracteres. Pasásela en persona.">
            <input
              id={`clave-${u.id}`}
              type="text"
              autoComplete="new-password"
              className={claseInput}
              value={clave}
              maxLength={72}
              onChange={(e) => setClave(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && guardarClave()}
            />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton secundario disabled={ocupado} onClick={() => setClave(null)}>
              Cancelar
            </Boton>
            <Boton disabled={ocupado} onClick={guardarClave}>
              {ocupado ? "Guardando..." : "Guardar contraseña"}
            </Boton>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm font-medium">
          {error}
        </p>
      )}
    </li>
  );
}

function NuevoUsuario({ onCreado, avisar }) {
  const [f, setF] = useState({ nombre: "", email: "", password: "", rol: "cantina" });
  const [errores, setErrores] = useState({});
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));

  async function crear(e) {
    e.preventDefault();
    const err = {};
    if (f.nombre.trim().length < 2) err.nombre = "Poné el nombre";
    if (!/^\S+@\S+\.\S+$/.test(f.email.trim())) err.email = "Revisá el email";
    if (f.password.length < 8) err.password = "Al menos 8 caracteres";
    setErrores(err);
    if (Object.keys(err).length) return;
    setOcupado(true);
    setError(null);
    try {
      const u = await api.crear({ ...f, nombre: f.nombre.trim(), email: f.email.trim() });
      avisar(`${u.nombre} creado como ${NOMBRE_ROL[u.rol]}`);
      setF({ nombre: "", email: "", password: "", rol: f.rol });
      onCreado(u);
    } catch (e2) {
      setError(e2.message); // ej: "Ya hay un usuario con ese email"
    } finally {
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={crear} className="bg-negro border border-gris rounded-2xl p-4 md:p-5 grid gap-3 content-start" noValidate>
      <h2 className="text-[24px]">Usuario nuevo</h2>
      <Campo etiqueta="Nombre" id="nu-nombre" error={errores.nombre}>
        <input id="nu-nombre" className={claseInput} maxLength={80} value={f.nombre} aria-invalid={!!errores.nombre} onChange={(e) => set("nombre", e.target.value)} />
      </Campo>
      <Campo etiqueta="Email (con esto entra)" id="nu-email" error={errores.email}>
        <input id="nu-email" type="email" inputMode="email" autoComplete="off" className={claseInput} maxLength={120} value={f.email} aria-invalid={!!errores.email} onChange={(e) => set("email", e.target.value)} />
      </Campo>
      <Campo etiqueta="Contraseña" id="nu-pass" error={errores.password} ayuda="Al menos 8 caracteres">
        <input id="nu-pass" type="text" autoComplete="new-password" className={claseInput} maxLength={72} value={f.password} aria-invalid={!!errores.password} onChange={(e) => set("password", e.target.value)} />
      </Campo>
      <fieldset className="grid gap-1.5">
        <legend className="text-xs text-tenue font-medium mb-1">Rol</legend>
        {ROLES.map((r) => (
          <label key={r.id} className={`flex items-start gap-2.5 p-2.5 rounded-xl border cursor-pointer ${f.rol === r.id ? "border-naranja bg-naranja/5" : "border-gris"}`}>
            <input type="radio" name="rol" className="accent-[#f05c2b] mt-1" checked={f.rol === r.id} onChange={() => set("rol", r.id)} />
            <span className="leading-tight">
              <b className="block text-sm font-semibold">{r.nombre}</b>
              <small className="text-tenue text-xs">{r.que}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {error && (
        <p role="alert" className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm">
          {error}
        </p>
      )}
      <Boton grande type="submit" disabled={ocupado}>
        {ocupado ? "Creando..." : "Crear usuario"}
      </Boton>
    </form>
  );
}

export default function Usuarios({ sesion }) {
  const [lista, setLista] = useState(null);
  const [error, setError] = useState(null);
  const { avisos, avisar } = useAvisos();

  const cargar = useCallback(async () => {
    try {
      setLista(await api.lista());
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const cambio = (u) => setLista((l) => l.map((x) => (x.id === u.id ? u : x)));
  // Activos primero, después por nombre
  const ordenada = lista && [...lista].sort((a, b) => Number(b.activo) - Number(a.activo) || a.nombre.localeCompare(b.nombre));

  return (
    <Marco sesion={sesion}>
      <AvisoConexion conectado error={error} onReintentar={cargar} />
      <Titulo bajada="Cada uno entra con su email. Si alguien se olvidó la contraseña, cambiásela acá.">Usuarios</Titulo>
      <div className="px-4 md:px-6 py-4 pb-24 grid lg:grid-cols-[1fr_380px] gap-4 items-start">
        <ul className="grid gap-2.5">
          {!ordenada ? (
            <>
              <Esqueleto alto="h-28" />
              <Esqueleto alto="h-28" />
            </>
          ) : (
            ordenada.map((u) => <UsuarioFila key={u.id} u={u} soyYo={u.id === sesion.usuario.id} onCambio={cambio} avisar={avisar} />)
          )}
        </ul>
        <NuevoUsuario onCreado={(u) => setLista((l) => [...(l || []), u])} avisar={avisar} />
      </div>
      <Avisos avisos={avisos} />
    </Marco>
  );
}
