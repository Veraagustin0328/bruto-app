import { Route, Routes } from "react-router-dom";

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
      <Route path="/" element={<Provisoria nombre="Tienda" />} />
      <Route path="/pedido/:codigo" element={<Provisoria nombre="Seguimiento" />} />
      <Route path="/panel/login" element={<Provisoria nombre="Login" />} />
      <Route path="/panel" element={<Provisoria nombre="Panel de la cantina" />} />
      <Route path="/cocina" element={<Provisoria nombre="Cocina" />} />
      <Route path="*" element={<Provisoria nombre="No existe esta página" />} />
    </Routes>
  );
}
