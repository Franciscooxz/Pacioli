"""Helpers monetarios. Todo el dinero es Decimal con 2 decimales y ROUND_HALF_UP.

Por que no float: los float binarios no representan exactamente cantidades decimales
(0.1 + 0.2 != 0.3), y en contabilidad un centavo de descuadre es un error real. Por
eso el CLAUDE.md prohibe float para dinero en todo el sistema.

Por que ROUND_HALF_UP y no el redondeo por defecto de Python: Python usa banker's
rounding (ROUND_HALF_EVEN), que redondea 2.5 -> 2. La norma contable colombiana y la
intuicion del contador esperan 2.5 -> 3. Forzamos ROUND_HALF_UP para coincidir.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Dos decimales: la escala de NUMERIC(19,2) en la base.
MONEY_QUANTUM = Decimal("0.01")


def to_money(value: Decimal | int | str) -> Decimal:
    """Normaliza un valor a Decimal con 2 decimales y ROUND_HALF_UP.

    Acepta Decimal, int o str (nunca float, para no arrastrar imprecision binaria).
    """
    if isinstance(value, float):  # defensa explicita: float esta prohibido
        raise TypeError("No se permite float para dinero; use Decimal, int o str.")
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
