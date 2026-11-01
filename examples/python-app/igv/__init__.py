"""Cálculo de IGV (Perú) con redondeo comercial a 2 decimales."""
from decimal import ROUND_HALF_UP, Decimal

TASA_IGV = Decimal("0.18")
_CENTIMO = Decimal("0.01")

__all__ = ["TASA_IGV", "desglosar", "agregar_igv"]


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTIMO, rounding=ROUND_HALF_UP)


def agregar_igv(base: Decimal | str | int, tasa: Decimal = TASA_IGV) -> dict[str, Decimal]:
    """Calcula IGV y total a partir de un valor de venta sin impuestos."""
    base = Decimal(str(base))
    if base < 0:
        raise ValueError("el monto no puede ser negativo")
    igv = _redondear(base * tasa)
    base = _redondear(base)
    return {"base": base, "igv": igv, "total": base + igv}


def desglosar(total: Decimal | str | int, tasa: Decimal = TASA_IGV) -> dict[str, Decimal]:
    """Separa un precio con IGV incluido en base imponible e impuesto."""
    total = Decimal(str(total))
    if total < 0:
        raise ValueError("el monto no puede ser negativo")
    base = _redondear(total / (1 + tasa))
    total = _redondear(total)
    return {"base": base, "igv": total - base, "total": total}
