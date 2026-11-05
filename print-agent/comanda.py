"""
Arma el texto de la comanda, como la de docs/BRUTO-pantallas.html.
48 caracteres de ancho: papel de 80 mm con la letra normal de las ticketeras.

Devuelve una lista de renglones (Renglon), cada uno con su estilo,
así la impresora de verdad puede poner negrita, letra grande o invertida
y la "impresora" de consola lo muestra como texto.
"""
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

ANCHO = 48

# Mendoza es UTC-3 todo el año (Argentina no cambia la hora)
MENDOZA = timezone(timedelta(hours=-3))


@dataclass
class Renglon:
    texto: str
    negrita: bool = False
    grande: bool = False  # doble alto y ancho en la ticketera
    invertido: bool = False  # blanco sobre negro (la ubicación)
    centrado: bool = False


def precio(n) -> str:
    # 29000 → "$29.000"
    return "$" + f"{round(float(n)):,}".replace(",", ".")


def fecha_local(iso: str) -> datetime:
    # El backend manda la fecha con zona; si viene sin zona es UTC
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MENDOZA)


def telefono(t: str) -> str:
    d = "".join(c for c in (t or "") if c.isdigit())
    return f"{d[:3]} {d[3:6]} {d[6:]}" if len(d) == 10 else d


def partir(texto: str, ancho: int = ANCHO, sangria: str = "") -> list[str]:
    return textwrap.wrap(texto, width=ancho, initial_indent=sangria, subsequent_indent=sangria) or [sangria]


def separador() -> Renglon:
    return Renglon("-" * ANCHO)


def armar_comanda(pedido: dict) -> list[Renglon]:
    r: list[Renglon] = []
    mp = pedido["metodo_pago"] == "mercadopago"
    pagado = pedido["estado_pago"] == "aprobado"

    r.append(Renglon("BRUTO · FOOD & GRILL", negrita=True, centrado=True))
    cuando = fecha_local(pedido["created_at"]).strftime("%d/%m %H:%M")
    r.append(Renglon(f"{cuando} · {'Mercado Pago' if mp else 'Efectivo'}", centrado=True))
    r.append(separador())
    r.append(Renglon(f"COMANDA #{pedido['numero']:03d}", negrita=True, grande=True, centrado=True))

    # La ubicación en negro y bien grande, para el que sale con la bandeja.
    # En letra grande entran la mitad de caracteres por renglón
    if pedido["modo"] == "comer_adentro":
        r.append(Renglon("COMER ADENTRO", negrita=True, invertido=True, centrado=True))
        for linea in partir((pedido.get("ubicacion") or "").upper(), ANCHO // 2):
            r.append(Renglon(linea, negrita=True, grande=True, invertido=True, centrado=True))
    else:
        r.append(Renglon("TAKE AWAY · RETIRA EN LA CANTINA", negrita=True, invertido=True, centrado=True))

    r.append(Renglon(f"{pedido['nombre']} {pedido['apellido']}"))
    if pedido.get("telefono"):
        r.append(Renglon(f"Tel {telefono(pedido['telefono'])}"))
    r.append(separador())

    for item in pedido["items"]:
        nombre = item["nombre_producto"].upper()
        extras = []
        for op in item["opciones"]:
            # El tamaño va pegado al nombre: "ANIMAL DOBLE", como la maqueta
            if op["nombre_grupo"].lower().startswith("tama"):
                nombre += f" {op['nombre_opcion'].upper()}"
            else:
                cant = f"{op['cantidad']}x " if op["cantidad"] > 1 else ""
                extras.append(f"+ {cant}{op['nombre_opcion']}")
        for linea in partir(f"{item['cantidad']}x {nombre}", ANCHO // 2):
            r.append(Renglon(linea, negrita=True, grande=True))
        for extra in extras:
            r.extend(Renglon(l) for l in partir(extra, sangria="   "))
        if item.get("nota"):
            r.extend(Renglon(l, negrita=True) for l in partir(f"** {item['nota'].upper()} **", sangria="   "))
    if pedido.get("notas"):
        r.append(Renglon(""))
        r.extend(Renglon(l, negrita=True) for l in partir(f"NOTA: {pedido['notas'].upper()}"))

    r.append(separador())
    izq = "PAGADO" if pagado else "COBRAR"
    der = precio(pedido["total"])
    r.append(Renglon(izq + der.rjust(ANCHO - len(izq)), negrita=True))
    return r


def como_texto(renglones: list[Renglon]) -> str:
    """La comanda en texto plano de 48 columnas (para la consola y el archivo)."""
    salida = []
    for rg in renglones:
        texto = rg.texto
        if rg.centrado:
            texto = texto.center(ANCHO)
        if rg.invertido:
            # En texto no hay fondo negro: lo marco con bloques a los costados
            texto = "█" + texto.strip().center(ANCHO - 2) + "█"
        salida.append(texto[:ANCHO].rstrip())
    return "\n".join(salida)
