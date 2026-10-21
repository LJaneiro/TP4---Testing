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
    "DEBUG100": {
        "tipo": "porcentaje",
        "valor": Decimal("1.0"),
        "vence": date(2099, 12, 31),
    },
}

ENVIOS = {
    "CABA": 2500,
    "GBA": 4000,
    "INTERIOR": 6500,
    "RETIRO": 0,
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


def calcular_descuento(subtotal, cantidad_prendas, cupon=None, fecha=date.today()):
    descuento = Decimal("0.00")

    if cantidad_prendas > 5:
        descuento += subtotal * Decimal("0.10")

    if cupon != None:
        codigo = cupon.strip()

        if codigo not in CUPONES:
            raise CheckoutError("CUPON_INVALIDO", "El cupón no existe")

        datos = CUPONES[codigo]

        if datos["tipo"] == "porcentaje":
            if not fecha < datos["vence"]:
                raise CheckoutError("CUPON_VENCIDO", "El cupón está vencido")
            descuento += subtotal * datos["valor"]

        elif datos["tipo"] == "fijo":
            if subtotal < datos["minimo"]:
                raise CheckoutError(
                    "CUPON_MINIMO_NO_ALCANZADO",
                    f"El cupón requiere una compra mínima de ${datos['minimo']}",
                )
            descuento += datos["valor"]

    return descuento.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_envio(subtotal, zona):
    zona = zona.strip().upper()

    if zona not in ENVIOS:
        raise CheckoutError(
            "ZONA_INVALIDA",
            f"Zona inválida. Opciones: {ENVIOS.keys().join(', ')}",
        )

    if subtotal >= 60000:
        return 0

    return ENVIOS[zona]


def calcular_total(carrito, zona, cupon=None, fecha=date.today()):
    subtotal = calcular_subtotal(carrito)

    prendas = 0
    for item in carrito:
        prendas = prendas + item["cantidad"]

    descuento = calcular_descuento(subtotal, prendas, cupon, fecha)
    envio = calcular_envio(subtotal, zona)
    total = subtotal - descuento + envio

    resultado = {
        "subtotal": subtotal,
        "descuento": descuento,
        "envio": envio,
        "total": round(total, 2),
    }
    return resultado
