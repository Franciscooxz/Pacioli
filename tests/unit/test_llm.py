"""Tests del parseo de la respuesta del LLM (sin llamar al API)."""

from __future__ import annotations

from decimal import Decimal

from contaflow.classification.llm_classifier import _parse_suggestion


def test_parse_json_valido() -> None:
    s = _parse_suggestion('{"account_code": "511595", "confidence": 0.7, "rationale": "servicio"}')
    assert s.account_code == "511595"
    assert s.confidence == Decimal("0.7")
    assert s.rationale == "servicio"


def test_parse_con_cerca_de_texto() -> None:
    s = _parse_suggestion('Claro:\n```json\n{"account_code":"613505","confidence":0.9}\n```')
    assert s.account_code == "613505"
    assert s.confidence == Decimal("0.9")


def test_parse_confianza_fuera_de_rango_se_recorta() -> None:
    assert _parse_suggestion('{"account_code":"1","confidence":1.5}').confidence == Decimal("1")
    assert _parse_suggestion('{"account_code":"1","confidence":-0.3}').confidence == Decimal("0")


def test_parse_basura_sin_cuenta() -> None:
    s = _parse_suggestion("no hay json aqui")
    assert s.account_code is None
    assert s.confidence == Decimal("0")
