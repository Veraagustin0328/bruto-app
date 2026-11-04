"""
Todo lo de Mercado Pago (Checkout Pro).

El flujo:
1. El cliente confirma el pedido con MP → queda "pendiente_pago"
2. Le creamos una preferencia y lo mandamos al link de MP (init_point)
3. Paga. MP nos avisa por el webhook y además lo devuelve a la app
4. Le preguntamos a MP por ese pago (nunca le creemos al aviso solo)
   y si está aprobado y el monto cierra, el pedido pasa a "recibido"
"""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import mercadopago
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EstadoPago, EstadoPedido, MetodoPago, Pedido
from app.services.pedidos import PedidoInvalido, buscar_por_codigo

log = logging.getLogger("bruto.pagos")

class ErrorMercadoPago(Exception):
    """MP no respondió o respondió algo raro. No es culpa del cliente."""


def cliente_mp() -> mercadopago.SDK:
    if not settings.mp_access_token:
        raise ErrorMercadoPago("Falta MP_ACCESS_TOKEN en el .env")
    return mercadopago.SDK(settings.mp_access_token)


# ---------- 1. crear la preferencia ----------


def titulo_item(item) -> str:
    # "Animal (Doble, 2x Extra carne y queso)" para que el cliente vea lo que paga
    extras = [
        o.nombre_opcion if o.cantidad == 1 else f"{o.cantidad}x {o.nombre_opcion}"
        for o in item.opciones
    ]
    return f"{item.nombre_producto} ({', '.join(extras)})" if extras else item.nombre_producto


def crear_preferencia(db: Session, codigo: str) -> dict:
    pedido = buscar_por_codigo(db, codigo)
    if pedido is None:
        raise PedidoInvalido("No encontramos ese pedido")
    if pedido.metodo_pago != MetodoPago.mercadopago:
        raise PedidoInvalido("Este pedido se paga en efectivo")
    if pedido.estado != EstadoPedido.pendiente_pago:
        raise PedidoInvalido("Este pedido ya está pago o fue cancelado")

    # El link vence a la misma hora en que la tarea de B3 cancela el pedido
    vence = datetime.now(timezone.utc) + timedelta(minutes=settings.minutos_para_pagar)
    vuelta = f"{settings.frontend_url}/pedido/{pedido.codigo}"

    datos = {
        "items": [
            {
                "id": str(item.producto_id or item.id),
                "title": titulo_item(item),
                "quantity": item.cantidad,
                "unit_price": float(item.precio_unitario),
                "currency_id": "ARS",
            }
            for item in pedido.items
        ],
        "payer": {"name": pedido.nombre, "surname": pedido.apellido},
        # Con esto encontramos el pedido cuando MP nos avise
        "external_reference": pedido.codigo,
        "statement_descriptor": "BRUTO",
        "back_urls": {"success": vuelta, "pending": vuelta, "failure": vuelta},
        "expires": True,
        "expiration_date_to": vence.isoformat(timespec="milliseconds"),
    }

    # MP solo acepta volver solo (auto_return) y avisar (webhook) a direcciones https.
    # En tu compu con localhost no se mandan y se usa /verificar
    if settings.frontend_url.startswith("https://"):
        datos["auto_return"] = "approved"
    if settings.backend_url.startswith("https://"):
        datos["notification_url"] = f"{settings.backend_url}/api/pagos/webhook"

    try:
        respuesta = cliente_mp().preference().create(datos)
    except ErrorMercadoPago:
        raise
    except Exception as e:
        raise ErrorMercadoPago(f"No se pudo hablar con Mercado Pago: {e}")

    if respuesta.get("status") not in (200, 201):
        log.error("MP rechazó la preferencia: %s", respuesta.get("response"))
        raise ErrorMercadoPago("Mercado Pago no aceptó el pedido")

    pref = respuesta["response"]
    pedido.mp_preference_id = pref["id"]
    db.commit()

    # En las credenciales de prueba MP usa sandbox_init_point
    link = pref.get("sandbox_init_point") if settings.mp_access_token.startswith("TEST-") else None
    return {"preference_id": pref["id"], "link_pago": link or pref["init_point"]}


# ---------- 2. aplicar un pago que nos informa MP ----------


def aplicar_pago(db: Session, pago: dict) -> Pedido | None:
    """Recibe el pago tal cual lo devuelve la API de MP y actualiza el pedido.
    Devuelve el pedido si cambió algo, None si no hubo nada que hacer.
    Se puede llamar varias veces con el mismo pago sin romper nada."""
    codigo = pago.get("external_reference")
    if not codigo:
        return None

    pedido = db.scalar(select(Pedido).where(Pedido.codigo == codigo))
    if pedido is None:
        log.warning("Pago %s de un pedido que no existe: %s", pago.get("id"), codigo)
        return None

    # Ya estaba aprobado (MP avisa más de una vez el mismo pago)
    if pedido.estado_pago == EstadoPago.aprobado:
        return None

    estado = pago.get("status")

    if estado == "approved":
        pagado = Decimal(str(pago.get("transaction_amount", 0)))
        if abs(pagado - Decimal(pedido.total)) > Decimal("0.01"):
            # No debería pasar nunca. Si pasa, no se aprueba solo: lo ve la cantina
            log.error("Pedido #%s: MP cobró %s y el pedido es %s", pedido.numero, pagado, pedido.total)
            return None

        pedido.estado_pago = EstadoPago.aprobado
        pedido.mp_payment_id = str(pago.get("id"))
        if pedido.estado == EstadoPedido.pendiente_pago:
            pedido.estado = EstadoPedido.recibido  # ahora sí le cae a la cocina
        elif pedido.estado == EstadoPedido.cancelado:
            # Pagó tarde un pedido que ya se había cancelado: queda cancelado y pagado
            log.error("Pedido #%s: pagaron un pedido cancelado, hay que devolver la plata", pedido.numero)
        db.commit()
        return pedido

    if estado in ("rejected", "cancelled"):
        # El pedido sigue esperando el pago: puede probar con otra tarjeta
        pedido.estado_pago = EstadoPago.rechazado
        pedido.mp_payment_id = str(pago.get("id"))
        db.commit()
        return pedido

    # pending, in_process, etc.: todavía no hay nada que hacer
    return None


def evento_para_el_panel(pedido: Pedido) -> str:
    # aplicar_pago solo devuelve el pedido si cambió algo. Si quedó "recibido"
    # es porque recién se pagó: para la cantina es nuevo y tiene que sonar
    if pedido.estado == EstadoPedido.recibido and pedido.estado_pago == EstadoPago.aprobado:
        return "pedido_nuevo"
    return "pedido_actualizado"


def traer_pago(pago_id: str) -> dict | None:
    respuesta = cliente_mp().payment().get(pago_id)
    if respuesta.get("status") != 200:
        log.warning("MP no encontró el pago %s: %s", pago_id, respuesta.get("response"))
        return None
    return respuesta["response"]


def verificar_pedido(db: Session, codigo: str) -> Pedido | None:
    # Le pregunta a MP si hay algún pago aprobado para este pedido.
    # Lo usa el celu al volver de MP, por si el webhook todavía no llegó
    # (o no llega nunca, como en tu compu sin ngrok)
    respuesta = cliente_mp().payment().search({"external_reference": codigo, "sort": "date_created", "criteria": "desc"})
    if respuesta.get("status") != 200:
        raise ErrorMercadoPago("No se pudo consultar el pago en Mercado Pago")

    pagos = respuesta["response"].get("results", [])
    aprobado = next((p for p in pagos if p.get("status") == "approved"), None)
    return aplicar_pago(db, aprobado or (pagos[0] if pagos else {}))


# ---------- 3. firma del webhook ----------


def firma_valida(x_signature: str | None, x_request_id: str | None, data_id: str) -> bool:
    """Chequea que el aviso venga de verdad de Mercado Pago.
    Si no hay MP_WEBHOOK_SECRET configurado se acepta igual: no es grave
    porque después le preguntamos a MP por el pago, nunca le creemos al aviso."""
    if not settings.mp_webhook_secret:
        return True
    if not x_signature:
        return False

    partes = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False

    manifiesto = f"id:{data_id.lower()};request-id:{x_request_id or ''};ts:{ts};"
    esperado = hmac.new(settings.mp_webhook_secret.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
