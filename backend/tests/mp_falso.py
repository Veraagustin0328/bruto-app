"""Un Mercado Pago de mentira para los tests: responde como el SDK de verdad."""


class _Preferencias:
    def __init__(self, mp):
        self.mp = mp

    def create(self, datos):
        self.mp.preferencias_creadas.append(datos)
        if self.mp.falla:
            return {"status": 400, "response": {"message": "algo salió mal"}}
        return {
            "status": 201,
            "response": {
                "id": "pref-123",
                "init_point": "https://www.mercadopago.com.ar/checkout?pref_id=pref-123",
                "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout?pref_id=pref-123",
            },
        }


class _Pagos:
    def __init__(self, mp):
        self.mp = mp

    def get(self, pago_id):
        pago = self.mp.pagos.get(str(pago_id))
        if pago is None:
            return {"status": 404, "response": {"message": "not found"}}
        return {"status": 200, "response": pago}

    def search(self, filtros):
        self.mp.busquedas += 1
        if self.mp.falla:
            return {"status": 500, "response": {}}
        codigo = filtros.get("external_reference")
        resultados = [p for p in self.mp.pagos.values() if p.get("external_reference") == codigo]
        return {"status": 200, "response": {"results": list(reversed(resultados))}}


class MPFalso:
    def __init__(self):
        self.pagos: dict[str, dict] = {}
        self.preferencias_creadas: list[dict] = []
        self.busquedas = 0
        self.falla = False

    def preference(self):
        return _Preferencias(self)

    def payment(self):
        return _Pagos(self)

    def agregar_pago(self, pago_id, codigo, monto, estado="approved"):
        self.pagos[str(pago_id)] = {
            "id": int(pago_id),
            "status": estado,
            "external_reference": codigo,
            "transaction_amount": monto,
        }
