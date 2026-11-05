// Piezas chicas que se repiten: stepper, radio, campo de texto

export function Stepper({ valor, onMenos, onMas, puedeMenos = true, puedeMas = true, etiqueta = "" }) {
  return (
    <span className="flex items-center gap-2 font-bold">
      <button
        type="button"
        onClick={onMenos}
        disabled={!puedeMenos}
        aria-label={`Sacar uno ${etiqueta}`.trim()}
        className="w-8 h-8 rounded-lg grid place-items-center bg-gris text-lg leading-none disabled:opacity-40"
      >
        −
      </button>
      <span className="num min-w-4 text-center" aria-live="polite">
        {valor}
      </span>
      <button
        type="button"
        onClick={onMas}
        disabled={!puedeMas}
        aria-label={`Sumar uno ${etiqueta}`.trim()}
        className="w-8 h-8 rounded-lg grid place-items-center bg-naranja text-white text-lg leading-none disabled:opacity-40 disabled:bg-gris"
      >
        +
      </button>
    </span>
  );
}

// El circulito de los radio (relleno naranja si está elegido)
export function Radio({ on, cuadrado = false }) {
  return (
    <span
      aria-hidden="true"
      className={`w-[18px] h-[18px] flex-none border-2 grid place-items-center ${
        cuadrado ? "rounded-[5px]" : "rounded-full"
      } ${on ? "border-naranja bg-naranja shadow-[inset_0_0_0_3px_var(--color-carbon)]" : "border-linea"}`}
    />
  );
}

export function Campo({ etiqueta, id, error, ayuda, children }) {
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-xs text-tenue font-medium">
        {etiqueta}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-naranja">{error}</p>
      ) : (
        ayuda && <p className="text-xs text-tenue">{ayuda}</p>
      )}
    </div>
  );
}

// Clases del input de la marca (fondo carbón, borde naranja al foco)
export const claseInput =
  "w-full px-3 py-2.5 rounded-xl bg-carbon border border-linea text-[15px] placeholder:text-[#6f6660] outline-none focus:border-naranja focus:ring-3 focus:ring-naranja/15 aria-[invalid=true]:border-naranja";
