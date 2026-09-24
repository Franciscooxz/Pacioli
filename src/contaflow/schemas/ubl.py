"""Modelos Pydantic con el resultado del parseo de un documento UBL 2.1.

Todos los montos son Decimal (nunca float), como exige el CLAUDE.md. Los campos de
dinero usan max_digits=19, decimal_places=2 (la escala de NUMERIC(19,2) en la base).
El parser es fiel al XML: doc_type refleja la naturaleza DIAN del documento; la
perspectiva compra/venta se decide despues, en el pipeline, comparando NITs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from contaflow.models.enums import DocType, TaxCategory

# Dinero: 2 decimales, hasta 19 digitos. DIAN emite importes con 2 decimales.
Money = Annotated[Decimal, Field(max_digits=19, decimal_places=2)]
# Cantidades y precios unitarios admiten mas decimales que el dinero contable.
Quantity = Annotated[Decimal, Field(max_digits=19, decimal_places=6)]
Percent = Annotated[Decimal, Field(max_digits=6, decimal_places=3)]
# Tasa de cambio (TRM): pesos por unidad de la moneda extranjera. 6 decimales.
ExchangeRate = Annotated[Decimal, Field(max_digits=19, decimal_places=6)]


class TaxDetail(BaseModel):
    """Un renglon de impuesto o retencion.

    is_withholding distingue las retenciones (Retefuente/ReteIVA/ReteICA, que vienen en
    cac:WithholdingTaxTotal) de los impuestos como IVA (cac:TaxTotal).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    tax_name: str  # nombre tal cual en el XML, p. ej. "IVA", "ReteICA"
    category: TaxCategory
    is_withholding: bool
    percent: Percent
    taxable_amount: Money
    tax_amount: Money
    # Municipio para ICA/ReteICA. Se poblara cuando validemos la estructura real (DIAN).
    municipality: str | None = None


class DocumentLine(BaseModel):
    """Una linea del documento (cac:InvoiceLine / CreditNoteLine / DebitNoteLine)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    line_id: str
    description: str | None
    quantity: Quantity
    unit_price: Money
    line_total: Money


class ParsedDocument(BaseModel):
    """Documento electronico ya parseado, listo para persistir/clasificar."""

    model_config = ConfigDict(str_strip_whitespace=True)

    cufe: str
    document_number: str
    doc_type: DocType
    issue_date: date
    issuer_nit: str
    issuer_name: str | None
    receiver_nit: str | None
    currency: str
    # TRM cuando la moneda no es COP y el XML la trae (cac:PaymentExchangeRate). None si
    # es COP o si el XML no la incluye (en ese caso el posting la pide a un proveedor).
    exchange_rate: ExchangeRate | None = None
    subtotal: Money
    total_tax: Money  # suma de impuestos NO retenciones (IVA, consumo)
    total_withholding: Money = Decimal("0")  # suma de retenciones
    total: Money
    taxes: list[TaxDetail] = Field(default_factory=list)  # incluye impuestos y retenciones
    lines: list[DocumentLine] = Field(default_factory=list)
    # Advertencias no fatales (p. ej. subtotal + impuestos != total). No abortan el
    # parseo, pero marcan el documento para revision humana.
    warnings: list[str] = Field(default_factory=list)
