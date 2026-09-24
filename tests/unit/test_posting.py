"""Tests del armado del asiento (logica pura, sin Odoo ni base)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from contaflow.core.exceptions import PostingError
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import DocType, TaxCategory
from contaflow.odoo.posting import (
    PostingAccounts,
    PostingSide,
    build_move_lines,
    build_sale_move_lines,
    posting_side,
    reverse_lines,
)

ACCOUNTS = PostingAccounts(payable="220505", iva="240810", retefuente="236540", reteica="236805")
SALE_ACCOUNTS = PostingAccounts(
    receivable="130505",
    iva_generado="240805",
    retefuente_favor="135515",
    reteica_favor="135518",
)


def _tax(category: TaxCategory, amount: str, *, withholding: bool) -> DocumentTax:
    return DocumentTax(
        category=category,
        is_withholding=withholding,
        tax_name=category.value,
        percent=Decimal("19.00"),
        taxable_amount=Decimal("1000000.00"),
        tax_amount=Decimal(amount),
    )


def test_asiento_balanceado_con_iva_y_retenciones() -> None:
    taxes = [
        _tax(TaxCategory.IVA, "190000.00", withholding=False),
        _tax(TaxCategory.RETEFUENTE, "25000.00", withholding=True),
        _tax(TaxCategory.RETEICA, "9660.00", withholding=True),
    ]
    lines = build_move_lines(Decimal("1000000.00"), "511595", taxes, ACCOUNTS)

    debit = sum((line.debit for line in lines), Decimal("0"))
    credit = sum((line.credit for line in lines), Decimal("0"))
    assert debit == credit  # el asiento cuadra

    payable = next(line for line in lines if line.account_code == "220505")
    # base + IVA - retenciones = 1.000.000 + 190.000 - 34.660
    assert payable.credit == Decimal("1155340.00")


def test_falta_cuenta_iva_lanza_error() -> None:
    accounts_sin_iva = PostingAccounts(payable="220505")
    taxes = [_tax(TaxCategory.IVA, "190000.00", withholding=False)]
    with pytest.raises(PostingError):
        build_move_lines(Decimal("1000000.00"), "511595", taxes, accounts_sin_iva)


def test_asiento_venta_balanceado() -> None:
    taxes = [
        _tax(TaxCategory.IVA, "190000.00", withholding=False),
        _tax(TaxCategory.RETEFUENTE, "25000.00", withholding=True),
        _tax(TaxCategory.RETEICA, "9660.00", withholding=True),
    ]
    lines = build_sale_move_lines(Decimal("1000000.00"), "413595", taxes, SALE_ACCOUNTS)

    debit = sum((line.debit for line in lines), Decimal("0"))
    credit = sum((line.credit for line in lines), Decimal("0"))
    assert debit == credit

    cxc = next(line for line in lines if line.account_code == "130505")
    # base + IVA - retenciones a favor = 1.000.000 + 190.000 - 34.660
    assert cxc.debit == Decimal("1155340.00")
    assert cxc.credit == Decimal("0")
    # El ingreso va al credito por el subtotal.
    ingreso = next(line for line in lines if line.account_code == "413595")
    assert ingreso.credit == Decimal("1000000.00")


def test_venta_falta_iva_generado_lanza_error() -> None:
    accounts_sin_iva = PostingAccounts(receivable="130505")
    taxes = [_tax(TaxCategory.IVA, "190000.00", withholding=False)]
    with pytest.raises(PostingError):
        build_sale_move_lines(Decimal("1000000.00"), "413595", taxes, accounts_sin_iva)


def test_reverse_lines_invierte_y_mantiene_cuadre() -> None:
    taxes = [_tax(TaxCategory.IVA, "190000.00", withholding=False)]
    lines = build_move_lines(Decimal("1000000.00"), "511595", taxes, ACCOUNTS)
    invertidas = reverse_lines(lines)

    for original, invertida in zip(lines, invertidas, strict=True):
        assert invertida.debit == original.credit
        assert invertida.credit == original.debit

    debit = sum((line.debit for line in invertidas), Decimal("0"))
    credit = sum((line.credit for line in invertidas), Decimal("0"))
    assert debit == credit


def test_posting_side_factura() -> None:
    assert (
        posting_side(DocType.FACTURA_COMPRA, "900555111", "800111222", "900555111")
        is PostingSide.PURCHASE
    )
    assert (
        posting_side(DocType.FACTURA_VENTA, "900555111", "900555111", "800111222")
        is PostingSide.SALE
    )


def test_posting_side_nota_por_nit() -> None:
    # La empresa es el receptor -> compra.
    assert (
        posting_side(DocType.NOTA_CREDITO, "800111222", "900555111", "800111222")
        is PostingSide.PURCHASE
    )
    # La empresa es el emisor -> venta.
    assert (
        posting_side(DocType.NOTA_CREDITO, "900555111", "900555111", "800111222")
        is PostingSide.SALE
    )


def test_posting_side_nota_indeterminada() -> None:
    with pytest.raises(PostingError):
        posting_side(DocType.NOTA_DEBITO, "700000000", "900555111", "800111222")
