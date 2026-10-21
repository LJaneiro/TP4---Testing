import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


class CheckoutError(Exception):
    def __init__(self, code, mensaje):
        super().__init__(mensaje)
        self.code = code
        self.mensaje = mensaje


CATALOGO = {
    "buzo": Decimal("24999.90"),
    "remera": Decimal("11999.50"),
    "campera": Decimal("47999.99"),
}

TALLES = ["XS", "S", "M", "L", "XL", "XXL"]

CUPONES = {
    "EGRESADOS2026": {
        "tipo": "porcentaje",
        "valor": Decimal("0.15"),
        "vence": date(2026, 11, 30),
    },
    "BIENVENIDA": {
        "tipo": "fijo",
        "valor": Decimal("3000.00"),
        "minimo": Decimal("20000.00"),
    },
}

ENVIOS = {
    "CABA": Decimal("2500.00"),
    "GBA": Decimal("4000.00"),
    "INTERIOR": Decimal("6500.00"),
    "RETIRO": Decimal("0.00"),
}


def validar_item(item):
    producto = item.get("producto")
    if producto not in CATALOGO:
        raise CheckoutError("PRODUCTO_INEXISTENTE", "El producto no existe")

    talle = item.get("talle")
    if not isinstance(talle, str) or talle.strip().upper() not in TALLES:
        raise CheckoutError("TALLE_INVALIDO", "El talle no es válido")

    cantidad = item.get("cantidad")
    if type(cantidad) is not int or not (1 <= cantidad <= 10):
        raise CheckoutError(
            "CANTIDAD_INVALIDA",
            "La cantidad debe estar entre 1 y 10",
        )

def calcular_subtotal(carrito):
    subtotal = Decimal("0.00")

    for item in carrito:
        validar_item(item)
        precio = CATALOGO[item["producto"]]
        subtotal += precio * item["cantidad"]

    return subtotal


def calcular_descuento(subtotal, cantidad_prendas, cupon=None, fecha=None):
    if fecha is None:
        fecha = date.today()

    descuento_cantidad = Decimal("0.00")
    descuento_cupon = Decimal("0.00")

    if cantidad_prendas >= 5:
        descuento_cantidad = subtotal * Decimal("0.10")

    if cupon is not None:
        codigo = cupon.strip().upper()

        if codigo:
            if codigo not in CUPONES:
                raise CheckoutError("CUPON_INVALIDO", "El cupón no existe")

            datos = CUPONES[codigo]

            if datos["tipo"] == "porcentaje":
                if fecha > datos["vence"]:
                    raise CheckoutError("CUPON_VENCIDO", "El cupón está vencido")

                descuento_cupon = subtotal * datos["valor"]

            elif datos["tipo"] == "fijo":
                if subtotal < datos["minimo"]:
                    raise CheckoutError(
                        "CUPON_MINIMO_NO_ALCANZADO",
                        "No se alcanza el mínimo del cupón",
                    )

                descuento_cupon = datos["valor"]

    descuento = max(descuento_cantidad, descuento_cupon)

    return descuento.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_envio(subtotal, zona):
    zona = zona.strip().upper()

    if zona not in ENVIOS:
        raise CheckoutError(
            "ZONA_INVALIDA",
            f"Zona inválida. Opciones: {', '.join(ENVIOS)}",
        )

    if subtotal >= Decimal("60000.00"):
        return Decimal("0.00")

    return ENVIOS[zona]

def calcular_total(carrito, zona, cupon=None, fecha=None):
    if not carrito:
        raise CheckoutError(
            "CARRITO_VACIO",
            "El carrito no puede estar vacío",
        )

    subtotal = calcular_subtotal(carrito)

    prendas = sum(item["cantidad"] for item in carrito)

    descuento = calcular_descuento(
        subtotal, prendas, cupon, fecha
    )

    envio = calcular_envio(subtotal - descuento, zona)

    total = subtotal - descuento + envio

    return {
        "subtotal": subtotal,
        "descuento": descuento,
        "envio": envio,
        "total": total.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
    }