import { Route, Routes } from "react-router-dom";
import Tienda from "./tienda/Tienda";
import { CarritoProvider } from "./tienda/carrito";
import Seguimiento from "./tienda/Seguimiento";
import Login from "./panel/Login";
import Panel from "./panel/Panel";
import { ROLES_PANEL, RutaProtegida } from "./panel/sesion";

// Por ahora cada ruta muestra su nombre, para ver que el router anda
function Provisoria({ nombre }) {
  return (
    <main className="min-h-dvh grid place-items-center p-6">
      <h1 className="text-5xl text-naranja">{nombre}</h1>
    </main>
  );
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
      <Route
        path="/panel"
        element={<RutaProtegida roles={ROLES_PANEL}>{(sesion) => <Panel sesion={sesion} />}</RutaProtegida>}
      />
      <Route path="/cocina" element={<Provisoria nombre="Cocina" />} />
      <Route path="*" element={<Provisoria nombre="No existe esta página" />} />
    </Routes>
  );
}
