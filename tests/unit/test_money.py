"""Tests del helper monetario (rule #3 del CLAUDE.md: dominio con test primero)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from contaflow.core.money import to_money


def test_to_money_agrega_dos_decimales() -> None:
    assert to_money(Decimal("10")) == Decimal("10.00")
    assert to_money("1500") == Decimal("1500.00")
    assert to_money(0) == Decimal("0.00")


def test_to_money_redondea_half_up_no_bankers() -> None:
    # Banker's rounding daria 1.00; nosotros exigimos ROUND_HALF_UP -> 1.01.
    assert to_money("1.005") == Decimal("1.01")
    assert to_money("2.675") == Decimal("2.68")


def test_to_money_rechaza_float() -> None:
    with pytest.raises(TypeError):
        to_money(1.005)  # type: ignore[arg-type]  # probamos justo el caso prohibido


def test_to_money_preserva_montos_grandes() -> None:
    # 17 enteros + 2 decimales = 19 digitos, el limite de NUMERIC(19,2).
    grande = Decimal("12345678901234567.89")
    assert to_money(grande) == grande
