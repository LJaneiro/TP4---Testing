
import json
import threading
import urllib.error
import urllib.request

import pytest

import api

RUTA = "/api/v1/pedidos"


@pytest.fixture
def url(tmp_path):
    servidor = api.crear_servidor(str(tmp_path / "tienda.db"), 0)

    hilo = threading.Thread(
        target=servidor.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
    )
    hilo.start()

    yield f"http://127.0.0.1:{servidor.server_address[1]}"

    servidor.shutdown()
    hilo.join(timeout=5)
    servidor.server_close()


def pedir(url, metodo, ruta, cuerpo=None, crudo=None):
    datos = (
        crudo
        if crudo is not None
        else json.dumps(cuerpo).encode("utf-8")
        if cuerpo is not None
        else None
    )

    req = urllib.request.Request(
        url + ruta,
        data=datos,
        method=metodo,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as respuesta:
            return respuesta.status, json.loads(
                respuesta.read() or b"null"
            )
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def compra(**cambios):
    cuerpo = {
        "email": "ana@mail.com",
        "zona": "CABA",
        "carrito": [
            {"producto": "buzo", "talle": "M", "cantidad": 1}
        ],
    }
    cuerpo.update(cambios)
    return cuerpo


# 1. Una ruta inexistente debe devolver 404

def test_una_ruta_inexistente_devuelve_404(url):
    status, cuerpo = pedir(url, "GET", "/api/v1/otra")

    assert status == 404
    assert cuerpo["error"]["code"] == "RUTA_INEXISTENTE"


# 2. Un POST en una ruta inexistente debe devolver 404

def test_post_ruta_inexistente_devuelve_404(url):
    status, cuerpo = pedir(
        url, "POST", "/api/v1/otra", compra()
    )

    assert status == 404
    assert cuerpo["error"]["code"] == "RUTA_INEXISTENTE"


# 3. Una compra valida debe devolver 201

def test_crear_pedido_valido_devuelve_201(url):
    status, cuerpo = pedir(url, "POST", RUTA, compra())

    assert status == 201
    assert isinstance(cuerpo["id"], int)
    assert cuerpo["subtotal"] == "24999.90"
    assert cuerpo["descuento"] == "0.00"
    assert cuerpo["envio"] == "2500.00"
    assert cuerpo["total"] == "27499.90"


# 4. Un pedido creado debe poder consultarse por GET

def test_crear_y_consultar_pedido(url):
    status_post, creado = pedir(
        url, "POST", RUTA, compra()
    )

    assert status_post == 201

    status_get, pedido = pedir(
        url, "GET", f"{RUTA}/{creado['id']}"
    )

    assert status_get == 200
    assert pedido["id"] == creado["id"]
    assert pedido["email"] == "ana@mail.com"
    assert pedido["total"] == 27499.90


# 5. El GET debe devolver los productos del pedido

def test_get_pedido_incluye_productos(url):
    carrito = [
        {"producto": "buzo", "talle": "M", "cantidad": 2},
        {"producto": "remera", "talle": "L", "cantidad": 1},
    ]

    status, creado = pedir(
        url, "POST", RUTA, compra(carrito=carrito)
    )

    assert status == 201

    status, pedido = pedir(
        url, "GET", f"{RUTA}/{creado['id']}"
    )

    assert status == 200
    assert len(pedido["items"]) == 2

    assert pedido["items"][0]["producto"] == "buzo"
    assert pedido["items"][0]["cantidad"] == 2
    assert pedido["items"][1]["producto"] == "remera"


# 6. Consultar un ID inexistente debe devolver 404

def test_pedido_inexistente_devuelve_404(url):
    status, cuerpo = pedir(url, "GET", f"{RUTA}/99999")

    assert status == 404
    assert cuerpo["error"]["code"] == "PEDIDO_INEXISTENTE"


# 7. Un producto inexistente debe devolver error de cliente

def test_producto_inexistente_devuelve_400(url):
    carrito = [
        {"producto": "gorra", "talle": "M", "cantidad": 1}
    ]

    status, cuerpo = pedir(
        url, "POST", RUTA, compra(carrito=carrito)
    )

    assert status == 422
    assert cuerpo["error"]["code"] == "PRODUCTO_INEXISTENTE"


# 8. Una cantidad invalida debe devolver 400

def test_cantidad_invalida_devuelve_400(url):
    carrito = [
        {"producto": "buzo", "talle": "M", "cantidad": 0}
    ]

    status, cuerpo = pedir(
        url, "POST", RUTA, compra(carrito=carrito)
    )

    assert status == 422
    assert cuerpo["error"]["code"] == "CANTIDAD_INVALIDA"


# 9. Una zona invalida debe devolver 400

def test_zona_invalida_devuelve_400(url):
    status, cuerpo = pedir(
        url, "POST", RUTA, compra(zona="MARTE")
    )

    assert status == 422
    assert cuerpo["error"]["code"] == "ZONA_INVALIDA"


# 10. Un carrito vacio debe devolver 400

def test_carrito_vacio_devuelve_400(url):
    status, cuerpo = pedir(
        url, "POST", RUTA, compra(carrito=[])
    )

    assert status == 422
    assert cuerpo["error"]["code"] == "CARRITO_VACIO"


# 11. Un JSON mal formado debe devolver 400

def test_json_invalido_devuelve_400(url):
    status, cuerpo = pedir(
        url,
        "POST",
        RUTA,
        crudo=b'{"email": "ana@mail.com",',
    )

    assert status == 400
    assert isinstance(cuerpo["error"], dict)
    assert "code" in cuerpo["error"]
    assert "message" in cuerpo["error"]


# 12. Un POST sin datos obligatorios debe devolver 400

def test_campos_obligatorios_faltantes(url):
    status, cuerpo = pedir(
        url,
        "POST",
        RUTA,
        {"email": "ana@mail.com"},
    )

    assert status == 400
    assert isinstance(cuerpo["error"], dict)


# 13. Una compra rechazada no debe crear pedidos

def test_compra_invalida_no_deja_pedido(url):
    carrito = [
        {"producto": "gorra", "talle": "M", "cantidad": 1}
    ]

    status, _ = pedir(
        url,
        "POST",
        RUTA,
        compra(carrito=carrito),
    )

    assert status == 422

    # Como esta base empieza vacia, el ID 1
    # no deberia existir despues del rechazo.
    status_get, _ = pedir(url, "GET", f"{RUTA}/1")

    assert status_get == 404

def test_talle_invalido_devuelve_422(url):
    carrito = [
        {"producto": "buzo", "talle": "XXXL", "cantidad": 1}
    ]

    status, cuerpo = pedir(
        url, "POST", RUTA, compra(carrito=carrito)
    )

    assert status == 422
    assert cuerpo["error"]["code"] == "TALLE_INVALIDO"


def test_fecha_invalida_devuelve_400(url):
    status, cuerpo = pedir(
        url, "POST", RUTA,
        compra(fecha="30/11/2026", cupon="EGRESADOS2026")
    )

    assert status == 400
    assert cuerpo["error"]["code"] == "FECHA_INVALIDA"


def test_fecha_valida_en_formato_iso(url):
    status, cuerpo = pedir(
        url, "POST", RUTA,
        compra(fecha="2026-11-30", cupon="EGRESADOS2026")
    )

    assert status == 201
    assert cuerpo["descuento"] == "3749.99"

def test_carrito_tipo_incorrecto_devuelve_400(url):
    status, cuerpo = pedir(
        url, "POST", RUTA,
        compra(carrito="texto"),
    )

    assert status == 400
    assert cuerpo["error"]["code"] == "DATOS_INCOMPLETOS"


@pytest.mark.parametrize("campo", ["email", "zona", "carrito"])
def test_campo_obligatorio_faltante_devuelve_400(url, campo):
    datos = compra()
    del datos[campo]

    status, cuerpo = pedir(url, "POST", RUTA, datos)

    assert status == 400
    assert cuerpo["error"]["code"] == "DATOS_INCOMPLETOS"