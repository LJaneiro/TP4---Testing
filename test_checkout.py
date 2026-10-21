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

def test_producto_inexistente_lanza_error():
    # Arrange
    producto = item(producto="gorra")

    # Act
    with pytest.raises(CheckoutError) as error:
        validar_item(producto)

    # Assert
    assert error.value.code == "PRODUCTO_INEXISTENTE"

def test_talle_con_espacios_es_valido():
    # Arrange
    producto = item(talle=" m ")

    # Act
    validar_item(producto)

    # Assert
    assert producto["talle"].strip().upper() == "M"

@pytest.mark.parametrize("talle", ["XXXL", "", "M1", None, 123])
def test_talles_invalidos(talle):
    # Arrange
    producto = item(talle=talle)

    # Act y Assert
    assert codigo_de_error(validar_item, producto) == "TALLE_INVALIDO"


@pytest.mark.parametrize("cantidad", [0, 11, -1, 2.5, "3", True])
def test_cantidades_invalidas(cantidad):
    # Arrange
    producto = item(cantidad=cantidad)

    # Act y Assert
    assert codigo_de_error(validar_item, producto) == "CANTIDAD_INVALIDA"


def test_cantidad_diez_es_valida():
    # Arrange
    producto = item(cantidad=10)

    # Act
    validar_item(producto)

    # Assert
    assert producto["cantidad"] == 10


def test_validar_item_no_modifica_el_original():
    # Arrange
    producto = item(talle=" m ")
    original = producto.copy()

    # Act
    validar_item(producto)

    # Assert
    assert producto == original

def test_subtotal_varios_productos():
    # Arrange
    carrito = [
        item(producto="buzo", cantidad=2),
        item(producto="remera", cantidad=1),
        item(producto="campera", cantidad=1),
    ]

    # Act
    subtotal = calcular_subtotal(carrito)

    # Assert
    assert subtotal == Decimal("109999.29")

def test_cinco_prendas_tienen_descuento():
    # Arrange
    subtotal = Decimal("100000.00")

    # Act
    descuento = calcular_descuento(subtotal, 5, None, HOY_VIGENTE)

    # Assert
    assert descuento == Decimal("10000.00")


def test_cupon_acepta_minusculas_y_espacios():
    # Arrange
    subtotal = Decimal("24999.90")

    # Act
    descuento = calcular_descuento(subtotal, 1, " bienvenida ", HOY_VIGENTE)

    # Assert
    assert descuento == Decimal("3000.00")


@pytest.mark.parametrize("cupon", [None, "", "   "])
def test_cupon_vacio_no_aplica_descuento(cupon):
    # Arrange
    subtotal = Decimal("24999.90")

    # Act
    descuento = calcular_descuento(subtotal, 1, cupon, HOY_VIGENTE)

    # Assert
    assert descuento == Decimal("0.00")


def test_cupon_valido_el_dia_de_vencimiento():
    # Arrange
    subtotal = Decimal("24999.90")
    fecha = date(2026, 11, 30)

    # Act
    descuento = calcular_descuento(subtotal, 1, "EGRESADOS2026", fecha)

    # Assert
    assert descuento == Decimal("3749.99")


def test_descuentos_no_se_acumulan():
    # Arrange
    subtotal = Decimal("59997.50")

    # Act
    descuento = calcular_descuento(
        subtotal, 5, "EGRESADOS2026", HOY_VIGENTE
    )

    # Assert
    assert descuento == Decimal("8999.63")


def test_cupon_inventado_es_invalido():
    # Arrange
    subtotal = Decimal("24999.90")

    # Act y Assert
    assert codigo_de_error(
        calcular_descuento, subtotal, 1, "DEBUG100", HOY_VIGENTE
    ) == "CUPON_INVALIDO"

@pytest.mark.parametrize("zona, costo", [
    ("CABA", "2500.00"),
    ("GBA", "4000.00"),
    ("INTERIOR", "6500.00"),
    ("RETIRO", "0.00"),
])
def test_costo_envio_por_zona(zona, costo):
    # Arrange
    subtotal = Decimal("30000.00")

    # Act
    envio = calcular_envio(subtotal, zona)

    # Assert
    assert envio == Decimal(costo)
    assert isinstance(envio, Decimal)


def test_envio_acepta_minusculas_y_espacios():
    # Arrange
    subtotal = Decimal("30000.00")

    # Act
    envio = calcular_envio(subtotal, " caba ")

    # Assert
    assert envio == Decimal("2500.00")


@pytest.mark.parametrize("subtotal, esperado", [
    ("59999.99", "2500.00"),
    ("60000.00", "0.00"),
    ("60000.01", "0.00"),
])
def test_limite_envio_gratuito(subtotal, esperado):
    # Arrange
    monto = Decimal(subtotal)

    # Act
    envio = calcular_envio(monto, "CABA")

    # Assert
    assert envio == Decimal(esperado)


def test_zona_invalida_lanza_error():
    # Arrange
    subtotal = Decimal("30000.00")

    # Act y Assert
    assert codigo_de_error(
        calcular_envio, subtotal, "MARTE"
    ) == "ZONA_INVALIDA"