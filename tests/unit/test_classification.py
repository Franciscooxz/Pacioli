"""Tests del matching de reglas (logica pura, sin base de datos)."""

from __future__ import annotations

from decimal import Decimal

from contaflow.classification.rule_engine import _rule_matches, select_rule
from contaflow.models.rule import ClassificationRule


def _rule(**kwargs: object) -> ClassificationRule:
    kwargs.setdefault("account_code", "511595")
    kwargs.setdefault("priority", 100)
    kwargs.setdefault("confidence", Decimal("0.90"))
    return ClassificationRule(**kwargs)


def test_match_por_issuer_nit() -> None:
    rule = _rule(issuer_nit="900123456")
    assert _rule_matches(rule, "900123456", "cualquier cosa") is True
    assert _rule_matches(rule, "800987654", "cualquier cosa") is False


def test_match_por_patron_regex() -> None:
    rule = _rule(match_pattern="arrend")
    assert _rule_matches(rule, "900", "Arrendamiento local comercial") is True
    assert _rule_matches(rule, "900", "Compra de papeleria") is False


def test_regla_sin_criterios_matchea_todo() -> None:
    rule = _rule()
    assert _rule_matches(rule, "900", "lo que sea") is True


def test_patron_invalido_no_matchea() -> None:
    rule = _rule(match_pattern="(sin-cerrar")
    assert _rule_matches(rule, "900", "texto") is False


def test_select_gana_mayor_prioridad() -> None:
    baja = _rule(issuer_nit="900", account_code="511595", priority=10)
    alta = _rule(issuer_nit="900", account_code="613505", priority=90)
    elegido = select_rule([baja, alta], "900", "")
    assert elegido is not None
    assert elegido.account_code == "613505"


def test_select_sin_match_devuelve_none() -> None:
    rule = _rule(issuer_nit="900")
    assert select_rule([rule], "800", "") is None
