import { useCallback, useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { EVENTO_SIN_SESION, auth, borrarSesion, leerSesion } from "../api";

// Quién puede entrar a cada pantalla. El admin entra a todo
export const ROLES_PANEL = ["admin", "cantina"];
export const ROLES_COCINA = ["admin", "cantina", "cocina"];

export const NOMBRE_ROL = {
  admin: "Admin",
  cantina: "Cantina",
  cocina: "Cocina",
  impresora: "Ticketera",
};

// Lleva al login si no hay sesión, si el token venció (401) o si el rol no entra
export function RutaProtegida({ roles, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [sesion, setSesion] = useState(leerSesion);
  const volver = encodeURIComponent(location.pathname);

  // Cuando cualquier llamada del panel da 401, el api.js avisa con este evento
  useEffect(() => {
    const alPerderla = () => {
      setSesion(null);
      navigate(`/panel/login?volver=${volver}&vencida=1`, { replace: true });
    };
    window.addEventListener(EVENTO_SIN_SESION, alPerderla);
    return () => window.removeEventListener(EVENTO_SIN_SESION, alPerderla);
  }, [navigate, volver]);

  // Chequeo de una que el token siga andando (y traigo el usuario actualizado)
  useEffect(() => {
    if (!sesion) return;
    auth
      .yo()
      .then((usuario) => setSesion((s) => (s ? { ...s, usuario } : s)))
      .catch(() => {}); // el 401 ya lo maneja el evento; si no hay internet, sigo
  }, [sesion?.token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sesion) return <Navigate to={`/panel/login?volver=${volver}`} replace />;

  if (!roles.includes(sesion.usuario?.rol)) {
    return (
      <main className="min-h-dvh grid place-items-center p-6 text-center">
        <div className="grid gap-3 justify-items-center">
          <p className="font-display text-3xl">Con este usuario no podés entrar acá</p>
          <p className="text-tenue text-sm">Entraste como {NOMBRE_ROL[sesion.usuario?.rol] || sesion.usuario?.rol}.</p>
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

  return children(sesion);
}

export function useSalir() {
  const navigate = useNavigate();
  return useCallback(() => {
    borrarSesion();
    navigate("/panel/login", { replace: true });
  }, [navigate]);
}
