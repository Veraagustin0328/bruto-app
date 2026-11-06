import { useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import Logo from "../componentes/Logo";
import { NOMBRE_ROL, pantallasDe, useSalir } from "./sesion";

// La barra de arriba de todo el panel: logo, pestañas según el rol, quién está y Salir.
// En el celu las pestañas van en una fila aparte que se desliza de costado
export default function Marco({ sesion, derecha, children, fondo = "bg-carbon" }) {
  const salir = useSalir();
  const usuario = sesion.usuario;
  const pantallas = pantallasDe(usuario.rol);
  const fila = useRef(null);
  const { pathname } = useLocation();

  // En el celu la fila de pestañas se desliza: que la de esta pantalla quede a la vista
  useEffect(() => {
    // Muevo solo la fila (scrollIntoView movía también la página para abajo)
    const centrar = () => {
      const nav = fila.current?.querySelector("nav");
      const activa = nav?.querySelector('[aria-current="page"]');
      if (nav && activa) nav.scrollLeft = activa.offsetLeft - nav.offsetLeft - (nav.clientWidth - activa.offsetWidth) / 2;
    };
    centrar();
    // Con la letra de Google cargada las pestañas son más anchas: centro de nuevo
    document.fonts?.ready.then(centrar);
  }, [pathname]);

  const pestanias = pantallas.length > 1 && (
    <nav aria-label="Secciones del panel" className="flex gap-1 overflow-x-auto sin-scrollbar lg:pr-0 pr-3">
      {pantallas.map((p) => (
        <NavLink
          key={p.ruta}
          to={p.ruta}
          end
          className={({ isActive }) =>
            `px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap ${isActive ? "bg-gris text-texto" : "text-tenue hover:text-texto"}`
          }
        >
          {p.nombre}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className={`min-h-dvh ${fondo}`}>
      <header className="border-b border-gris bg-negro">
        <div className="flex items-center gap-3 md:gap-6 px-4 md:px-6 py-3">
          <div className="flex-none">
            <Logo chico />
          </div>
          <div className="hidden lg:block flex-1 min-w-0">{pestanias}</div>
          <div className="flex-1 lg:hidden" />
          <div className="flex items-center gap-3 text-[12.5px] text-tenue">
            {derecha}
            <span className="hidden sm:inline whitespace-nowrap">
              {NOMBRE_ROL[usuario.rol]} · {usuario.nombre}
            </span>
            <button type="button" onClick={salir} className="text-tenue hover:text-texto underline-offset-2 hover:underline">
              Salir
            </button>
          </div>
        </div>
        {pestanias && (
          <div ref={fila} className="lg:hidden px-3 pb-2.5 -mt-0.5">
            {pestanias}
          </div>
        )}
      </header>
      {children}
    </div>
  );
}
