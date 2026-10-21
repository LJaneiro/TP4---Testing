from datetime import date
from decimal import Decimal

import pytest

from checkout import (
    CheckoutError,
    calcular_descuento,
    calcular_envio,
    calcular_subtotal,
    calcular_total,
    validar_item,
)

HOY_VIGENTE = date(2026, 10, 1)


def item(producto="buzo", talle="M", cantidad=1, **extra):
    return {"producto": producto, "talle": talle, "cantidad": cantidad, **extra}


def codigo_de_error(funcion, *args):
    with pytest.raises(CheckoutError) as error:
        funcion(*args)
    return error.value.code


def test_cantidad_cero_es_invalida():
    assert codigo_de_error(validar_item, item(cantidad=0)) == "CANTIDAD_INVALIDA"

def test_subtotal_dos_buzos_utiliza_decimal():
    # Arrange
    carrito = [item(producto="buzo", cantidad=2)]

    # Act
    subtotal = calcular_subtotal(carrito)

    # Assert
    assert isinstance(subtotal, Decimal)
    assert subtotal == Decimal("49999.80")

def test_descuento_redondea_medio_centavo_hacia_arriba():
    # Arrange
    subtotal = Decimal("11999.50")
    fecha = HOY_VIGENTE

    # Act
    descuento = calcular_descuento(subtotal, 1, "EGRESADOS2026", fecha)

    # Assert
    assert descuento == Decimal("1799.93")
    assert isinstance(descuento, Decimal)

def test_subtotal_ignora_precio_enviado_por_cliente():
    # Arrange
    carrito = [item(producto="buzo", cantidad=1, precio=1)]

    # Act
    subtotal = calcular_subtotal(carrito)

    # Assert
    assert subtotal == Decimal("24999.90")
