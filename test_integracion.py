
from datetime import date
from decimal import Decimal

import pytest

import pedidos
from checkout import CheckoutError

HOY_VIGENTE = date(2026, 10, 1)


@pytest.fixture
def ruta(tmp_path):
    return str(tmp_path / "tienda.db")


@pytest.fixture
def con(ruta):
    conexion = pedidos.conectar(ruta)
    pedidos.crear_esquema(conexion)
    yield conexion
    conexion.close()


def item(producto="buzo", talle="M", cantidad=1, **extra):
    return {
        "producto": producto,
        "talle": talle,
        "cantidad": cantidad,
        **extra,
    }


def contar(ruta, tabla):
    assert tabla in ("pedidos", "items")
    otra = pedidos.conectar(ruta)

    try:
        return otra.execute(
            f"SELECT COUNT(*) FROM {tabla}"
        ).fetchone()[0]
    finally:
        otra.close()


# 1. Consultar un pedido inexistente

def test_un_id_inexistente_devuelve_none(con):
    assert pedidos.obtener_pedido(con, 999) is None


# 2. Un pedido invalido no debe guardarse parcialmente

def test_pedido_invalido_no_se_guarda(con, ruta):
    carrito = [item(producto="gorra")]

    with pytest.raises(CheckoutError):
        pedidos.guardar_pedido(
            con,
            "cliente@gmail.com",
            carrito,
            "CABA",
            fecha=HOY_VIGENTE,
        )

    assert contar(ruta, "pedidos") == 0
    assert contar(ruta, "items") == 0


# 3. Un pedido valido debe quedar guardado completamente

def test_pedido_se_guarda_completo(con, ruta):
    carrito = [
        item(producto="buzo", cantidad=2),
        item(producto="remera", cantidad=1),
    ]

    pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    assert contar(ruta, "pedidos") == 1
    assert contar(ruta, "items") == 2


# 4. Prueba de diagnostico: confirmar manualmente los cambios

def test_items_visibles_despues_de_commit(con, ruta):
    carrito = [
        item(producto="buzo", cantidad=2),
        item(producto="remera", cantidad=1),
    ]

    pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()

    assert contar(ruta, "pedidos") == 1
    assert contar(ruta, "items") == 2


# 5. El precio unitario debe salir del catalogo

def test_precio_unitario_sale_del_catalogo(con):
    carrito = [item(producto="buzo", precio=1)]

    pedido_id = pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()
    pedido = pedidos.obtener_pedido(con, pedido_id)

    assert pedido["items"][0]["precio_unitario"] == Decimal("24999.90")


# 6. Los importes recuperados deben ser exactos

def test_importes_se_recuperan_exactamente(con):
    carrito = [item(producto="buzo")]

    pedido_id = pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()
    pedido = pedidos.obtener_pedido(con, pedido_id)

    assert pedido["subtotal"] == Decimal("24999.90")
    assert pedido["descuento"] == Decimal("0.00")
    assert pedido["envio"] == Decimal("2500.00")
    assert pedido["total"] == Decimal("27499.90")


# 7. Verificar que no haya errores de precision por usar float

def test_subtotal_no_tiene_error_de_float(con):
    carrito = [item(producto="campera")]

    pedido_id = pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()
    pedido = pedidos.obtener_pedido(con, pedido_id)

    assert pedido["subtotal"] == Decimal("47999.99")


# 8. Los datos del pedido deben quedar normalizados

def test_datos_se_guardan_normalizados(con):
    carrito = [item(producto="buzo", talle=" m ")]

    pedido_id = pedidos.guardar_pedido(
        con,
        " CLIENTE@GMAIL.COM ",
        carrito,
        " caba ",
        " bienvenida ",
        HOY_VIGENTE,
    )

    con.commit()
    pedido = pedidos.obtener_pedido(con, pedido_id)

    assert pedido["email"] == "cliente@gmail.com"
    assert pedido["zona"] == "CABA"
    assert pedido["cupon"] == "BIENVENIDA"
    assert pedido["items"][0]["talle"] == "M"


# 9. Una consulta por email solo debe devolver pedidos de ese cliente

def test_busqueda_email_filtra_cliente(con):
    carrito = [item(producto="buzo")]

    pedidos.guardar_pedido(
        con, "uno@gmail.com", carrito, "CABA",
        fecha=HOY_VIGENTE,
    )

    pedidos.guardar_pedido(
        con, "dos@gmail.com", carrito, "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()

    resultado = pedidos.pedidos_de(con, " UNO@GMAIL.COM ")

    assert len(resultado) == 1
    assert resultado[0]["email"] == "uno@gmail.com"


# 10. Los pedidos deben aparecer del mas reciente al mas antiguo

def test_pedidos_ordenados_del_mas_reciente(con):
    carrito = [item(producto="buzo")]

    primero = pedidos.guardar_pedido(
        con, "cliente@gmail.com", carrito, "CABA",
        fecha=HOY_VIGENTE,
    )

    segundo = pedidos.guardar_pedido(
        con, "cliente@gmail.com", carrito, "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()

    resultado = pedidos.pedidos_de(con, "cliente@gmail.com")

    assert [pedido["id"] for pedido in resultado] == [
        segundo,
        primero,
    ]


# 11. La busqueda por email no debe permitir inyeccion SQL

def test_busqueda_email_no_permite_inyeccion_sql(con):
    carrito = [item(producto="buzo")]

    pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()

    email_malicioso = "x' OR 1=1 --"

    resultado = pedidos.pedidos_de(con, email_malicioso)

    assert resultado == []


# 12. El precio recuperado debe mantener precision decimal

def test_precio_unitario_no_tiene_error_de_float(con):
    carrito = [item(producto="campera")]

    pedido_id = pedidos.guardar_pedido(
        con,
        "cliente@gmail.com",
        carrito,
        "CABA",
        fecha=HOY_VIGENTE,
    )

    con.commit()
    pedido = pedidos.obtener_pedido(con, pedido_id)

    assert pedido["items"][0]["precio_unitario"] == Decimal("47999.99")
