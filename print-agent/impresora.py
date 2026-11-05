"""
La "impresora". Por ahora no hay ticketera: la comanda sale por la consola
y se guarda en un archivo de texto.

Cuando tengamos el modelo de la ticketera, lo único que hay que cambiar es
imprimir() por algo así con python-escpos (ejemplo para una USB):

    from escpos.printer import Usb
    p = Usb(0x04b8, 0x0202)          # vendor y product id de la ticketera
    for r in renglones:
        p.set(align="center" if r.centrado else "left", bold=r.negrita,
              double_height=r.grande, double_width=r.grande, invert=r.invertido)
        p.text(r.texto + "\n")
    p.cut()
"""
from datetime import datetime
from pathlib import Path

from comanda import Renglon, como_texto

ARCHIVO = Path(__file__).resolve().parent / "comandas.txt"


def imprimir(renglones: list[Renglon]) -> None:
    texto = como_texto(renglones)
    print("\n" + texto + "\n" + "✂ " + "-" * 46 + "\n", flush=True)
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(f"# impresa {datetime.now():%d/%m %H:%M:%S}\n{texto}\n\n")
