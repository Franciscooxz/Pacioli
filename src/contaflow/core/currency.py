"""Conversion de moneda para contabilizar en COP.

Los montos se guardan en la moneda original del documento (fidelidad al XML). Odoo, en
cambio, se lleva en pesos: al contabilizar convertimos con la TRM (pesos por unidad de la
moneda extranjera) y ROUND_HALF_UP.

De donde sale la TRM:
1. Del propio XML (cac:PaymentExchangeRate), que el parser guarda en source_document.trm.
2. Si el XML no la trae, de un TrmProvider inyectado. Hoy solo existe el contrato; la
   fuente oficial (Superfinanciera / datos abiertos) se conecta en la Fase F.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from contaflow.core.money import to_money

COP = "COP"


@runtime_checkable
class TrmProvider(Protocol):
    """Fuente de TRM. rate_for devuelve pesos por unidad de `currency`, o None."""

    def rate_for(self, currency: str, on_date: date | None) -> Decimal | None: ...


def to_cop(amount: Decimal, rate: Decimal) -> Decimal:
    """Convierte un monto a COP aplicando la TRM, redondeando a 2 decimales."""
    return to_money(amount * rate)
