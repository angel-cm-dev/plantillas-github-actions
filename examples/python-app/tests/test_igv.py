from decimal import Decimal

import pytest

from igv import agregar_igv, desglosar


def test_agregar_igv():
    assert agregar_igv("100") == {"base": Decimal("100.00"), "igv": Decimal("18.00"), "total": Decimal("118.00")}


def test_desglosar_precio_con_igv():
    r = desglosar("118")
    assert r["base"] == Decimal("100.00")
    assert r["igv"] == Decimal("18.00")


def test_redondeo_comercial():
    r = desglosar("10")
    assert r["base"] + r["igv"] == r["total"] == Decimal("10.00")
    assert r["base"] == Decimal("8.47")


@pytest.mark.parametrize("funcion", [agregar_igv, desglosar])
def test_rechaza_negativos(funcion):
    with pytest.raises(ValueError):
        funcion("-1")
