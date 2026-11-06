import { Link, Route, Routes } from "react-router-dom";
import Tienda from "./tienda/Tienda";
import { CarritoProvider } from "./tienda/carrito";
import Seguimiento from "./tienda/Seguimiento";
import Login from "./panel/Login";
import Panel from "./panel/Panel";
import Cocina from "./panel/Cocina";
import Marco from "./panel/Marco";
import CartaPrecios from "./panel/carta/CartaPrecios";
import { Titulo } from "./panel/comunes";
import { RutaProtegida } from "./panel/sesion";

function NoExiste() {
  return (
    <main className="min-h-dvh grid place-items-center p-6 text-center">
      <div className="grid gap-4 justify-items-center">
        <h1 className="text-5xl text-naranja">No existe esta página</h1>
        <Link to="/" className="px-5 py-2.5 rounded-xl bg-naranja font-semibold">
          Ir a la carta
        </Link>
      </div>
    </main>
  );
}

// Lugar reservado mientras se arma cada pantalla
function Pronto({ sesion, titulo }) {
  return (
    <Marco sesion={sesion}>
      <Titulo bajada="Esta pantalla está en camino.">{titulo}</Titulo>
    </Marco>
  );
}

// Cada pantalla del panel con su control de sesión y rol (ver PANTALLAS en sesion.jsx)
function Protegida({ ruta, children }) {
  return <RutaProtegida ruta={ruta}>{children}</RutaProtegida>;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <CarritoProvider>
            <Tienda />
          </CarritoProvider>
        }
      />
      <Route path="/pedido/:codigo" element={<Seguimiento />} />
      <Route path="/panel/login" element={<Login />} />
      <Route path="/panel" element={<Protegida ruta="/panel">{(s) => <Panel sesion={s} />}</Protegida>} />
      <Route path="/cocina" element={<Protegida ruta="/cocina">{(s) => <Cocina sesion={s} />}</Protegida>} />
      <Route
        path="/panel/carta"
        element={<Protegida ruta="/panel/carta">{(s) => <CartaPrecios sesion={s} />}</Protegida>}
      />
      <Route path="/panel/caja" element={<Protegida ruta="/panel/caja">{(s) => <Pronto sesion={s} titulo="Caja del día" />}</Protegida>} />
      <Route
        path="/panel/config"
        element={<Protegida ruta="/panel/config">{(s) => <Pronto sesion={s} titulo="Configuración" />}</Protegida>}
      />
      <Route
        path="/panel/usuarios"
        element={<Protegida ruta="/panel/usuarios">{(s) => <Pronto sesion={s} titulo="Usuarios" />}</Protegida>}
      />
      <Route path="*" element={<NoExiste />} />
    </Routes>
  );
}
