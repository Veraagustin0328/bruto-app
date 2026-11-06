import { useCallback, useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { EVENTO_SIN_SESION, auth, borrarSesion, guardarSesion, leerSesion } from "../api";

export const NOMBRE_ROL = {
  admin: "Admin",
  cantina: "Cantina",
  cocina: "Cocina",
  impresora: "Ticketera",
};

// Las pantallas del panel y quién entra a cada una. El orden es el de las pestañas.
// La cantina ve la carta solo para prender y apagar productos (sin stock)
export const PANTALLAS = [
  { ruta: "/panel", nombre: "Pedidos", roles: ["admin", "cantina"] },
  { ruta: "/cocina", nombre: "Cocina", roles: ["admin", "cantina", "cocina"] },
  { ruta: "/panel/carta", nombre: "Carta y precios", nombreCantina: "Carta", roles: ["admin", "cantina"] },
  { ruta: "/panel/caja", nombre: "Caja", roles: ["admin", "cantina"] },
  { ruta: "/panel/config", nombre: "Configuración", roles: ["admin"] },
  { ruta: "/panel/usuarios", nombre: "Usuarios", roles: ["admin"] },
];

export function pantallasDe(rol) {
  return PANTALLAS.filter((p) => p.roles.includes(rol)).map((p) => ({
    ...p,
    nombre: rol === "cantina" && p.nombreCantina ? p.nombreCantina : p.nombre,
  }));
}

// A dónde va cada uno al entrar (o si cae en una pantalla que no es suya)
export function inicioDe(rol) {
  return rol === "cocina" ? "/cocina" : "/panel";
}

export function rolesDe(ruta) {
  return PANTALLAS.find((p) => p.ruta === ruta)?.roles || [];
}

// Lleva al login si no hay sesión o si el token venció (401).
// Si el rol no entra a esta pantalla, lo manda a la suya
export function RutaProtegida({ ruta, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [sesion, setSesion] = useState(leerSesion);
  const volver = encodeURIComponent(location.pathname);
  const roles = rolesDe(ruta);

  // Cuando cualquier llamada del panel da 401, el api.js avisa con este evento
  useEffect(() => {
    const alPerderla = () => {
      setSesion(null);
      navigate(`/panel/login?volver=${volver}&vencida=1`, { replace: true });
    };
    window.addEventListener(EVENTO_SIN_SESION, alPerderla);
    return () => window.removeEventListener(EVENTO_SIN_SESION, alPerderla);
  }, [navigate, volver]);

  // Chequeo de una que el token siga andando y traigo el usuario actualizado
  // (si Renzo le cambió el rol, acá se entera)
  useEffect(() => {
    if (!sesion) return;
    auth
      .yo()
      .then((usuario) => {
        setSesion((s) => (s ? { ...s, usuario } : s));
        guardarSesion(sesion.token, usuario);
      })
      .catch(() => {}); // el 401 ya lo maneja el evento; si no hay internet, sigo
  }, [sesion?.token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sesion) return <Navigate to={`/panel/login?volver=${volver}`} replace />;

  const rol = sesion.usuario?.rol;
  if (rol === "impresora" || !NOMBRE_ROL[rol]) {
    return (
      <main className="min-h-dvh grid place-items-center p-6 text-center">
        <div className="grid gap-3 justify-items-center">
          <p className="font-display text-3xl">Con este usuario no podés entrar al panel</p>
          <p className="text-tenue text-sm">Es el usuario de la ticketera.</p>
          <button
            type="button"
            onClick={() => {
              borrarSesion();
              navigate(`/panel/login?volver=${volver}`, { replace: true });
            }}
            className="px-5 py-2.5 rounded-xl bg-naranja font-semibold"
          >
            Entrar con otro usuario
          </button>
        </div>
      </main>
    );
  }

  if (!roles.includes(rol)) return <Navigate to={inicioDe(rol)} replace />;

  return children(sesion);
}

export function useSalir() {
  const navigate = useNavigate();
  return useCallback(() => {
    borrarSesion();
    navigate("/panel/login", { replace: true });
  }, [navigate]);
}
