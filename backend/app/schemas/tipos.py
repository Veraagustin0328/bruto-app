from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# En la base los precios son Decimal (para no perder centavos en las cuentas).
# Hacia el front salen como número, así no le llega "12500.00" como texto
Precio = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]
