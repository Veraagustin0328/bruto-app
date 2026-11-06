import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { auth, guardarSesion } from "../api";
import { Campo, claseInput } from "../componentes/Controles";
import Logo from "../componentes/Logo";
import { inicioDe } from "./sesion";

export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [entrando, setEntrando] = useState(false);
  const enviando = useRef(false);

  async function entrar(e) {
    e.preventDefault();
    if (enviando.current) return;
    if (!email.trim() || !password) {
      setError("Completá el email y la contraseña");
      return;
    }
    enviando.current = true;
    setEntrando(true);
    setError(null);
    try {
      const { access_token, usuario } = await auth.login(email.trim(), password);
      if (usuario.rol === "impresora") {
        setError("Ese usuario es solo para la ticketera, no entra al panel");
        return;
      }
      guardarSesion(access_token, usuario);
      // Vuelve a donde quería ir; si no, cada uno a su pantalla
      const volver = params.get("volver");
      const destino =
        volver && volver.startsWith("/") && !volver.startsWith("//")
          ? volver
          : inicioDe(usuario.rol);
      navigate(destino, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      enviando.current = false;
      setEntrando(false);
    }
  }

  return (
    <main className="min-h-dvh grid place-items-center p-5">
      <form onSubmit={entrar} className="w-full max-w-sm grid gap-4 p-6 rounded-2xl bg-carbon border border-gris">
        <div className="grid gap-2">
          <Logo />
          <h1 className="text-[34px] mt-2">Panel de la cantina</h1>
          {params.get("vencida") && (
            <p className="text-alerta text-sm">Se venció tu sesión, entrá de nuevo.</p>
          )}
        </div>
        <Campo etiqueta="Email" id="email">
          <input
            id="email"
            type="email"
            autoComplete="username"
            inputMode="email"
            className={`${claseInput} bg-negro`}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Contraseña" id="password">
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className={`${claseInput} bg-negro`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Campo>
        {error && (
          <p role="alert" className="p-3 rounded-xl bg-naranja/15 text-naranja text-sm">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={entrando}
          className="rounded-xl py-3 font-bold tracking-wide bg-naranja text-white disabled:opacity-60"
        >
          {entrando ? "ENTRANDO..." : "ENTRAR"}
        </button>
      </form>
    </main>
  );
}
