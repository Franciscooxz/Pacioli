"""Tests del parser UBL 2.1 (Entrega 3).

Cubren: factura simple, varias tarifas de IVA, nota credito, AttachedDocument anidado,
XML corrupto, descuadre de totales, proteccion XXE, CUFE ausente y raiz no soportada.
Los fixtures son sinteticos y anonimizados (ver tests/fixtures/xml/).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from contaflow.core.exceptions import (
    MalformedUblError,
    MissingCufeError,
    UnsupportedDocumentTypeError,
)
from contaflow.ingestion.ubl_parser import parse_ubl
from contaflow.models.enums import DocType, TaxCategory

FIXTURES = Path(__file__).parent.parent / "fixtures" / "xml"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_factura_simple() -> None:
    doc = parse_ubl(_load("factura_simple.xml"))

    assert doc.cufe.endswith("d7e8f90")
    assert len(doc.cufe) == 96
    assert doc.document_number == "SETP990000001"
    assert doc.doc_type is DocType.FACTURA_VENTA
    assert doc.issuer_nit == "900123456"
    assert doc.issuer_name == "Proveedor de Prueba SAS"
    assert doc.receiver_nit == "800987654"
    assert doc.currency == "COP"
    assert doc.subtotal == Decimal("100000.00")
    assert doc.total_tax == Decimal("19000.00")
    assert doc.total == Decimal("119000.00")
    assert len(doc.taxes) == 1
    assert doc.taxes[0].tax_name == "IVA"
    assert doc.taxes[0].category is TaxCategory.IVA
    assert doc.taxes[0].is_withholding is False
    assert doc.taxes[0].percent == Decimal("19.00")
    assert doc.total_withholding == Decimal("0")
    assert len(doc.lines) == 1
    assert doc.lines[0].description == "Servicio de consultoria"
    assert not doc.warnings


def test_todos_los_montos_son_decimal_no_float() -> None:
    doc = parse_ubl(_load("factura_simple.xml"))
    for value in (doc.subtotal, doc.total_tax, doc.total):
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)
    assert isinstance(doc.lines[0].line_total, Decimal)
    assert isinstance(doc.taxes[0].tax_amount, Decimal)


def test_factura_varias_tarifas_iva() -> None:
    doc = parse_ubl(_load("factura_multi_iva.xml"))

    assert doc.doc_type is DocType.FACTURA_VENTA
    assert len(doc.lines) == 3
    assert len(doc.taxes) == 3
    assert {t.percent for t in doc.taxes} == {
        Decimal("19.00"),
        Decimal("5.00"),
        Decimal("0.00"),
    }
    assert doc.total_tax == Decimal("29000.00")
    assert doc.subtotal == Decimal("350000.00")
    assert doc.total == Decimal("379000.00")
    assert not doc.warnings


def test_factura_con_retenciones() -> None:
    doc = parse_ubl(_load("factura_con_retenciones.xml"))

    assert doc.total_tax == Decimal("190000.00")  # IVA, no retencion
    assert doc.total_withholding == Decimal("34660.00")  # Retefuente + ReteICA
    assert not doc.warnings  # subtotal + IVA == TaxInclusiveAmount

    withholdings = [t for t in doc.taxes if t.is_withholding]
    categorias = {t.category for t in withholdings}
    assert categorias == {TaxCategory.RETEFUENTE, TaxCategory.RETEICA}

    iva = [t for t in doc.taxes if not t.is_withholding]
    assert len(iva) == 1
    assert iva[0].category is TaxCategory.IVA


def test_nota_credito() -> None:
    doc = parse_ubl(_load("nota_credito.xml"))

    assert doc.doc_type is DocType.NOTA_CREDITO
    assert doc.document_number == "NC990000001"
    assert doc.total == Decimal("59500.00")
    assert len(doc.lines) == 1
    assert doc.lines[0].description == "Devolucion de servicio"


def test_attached_document_se_desanida() -> None:
    doc = parse_ubl(_load("attached_document.xml"))

    # Debe devolver la factura EMBEBIDA, no el contenedor.
    assert doc.document_number == "AD990000009"
    assert doc.doc_type is DocType.FACTURA_VENTA
    assert doc.issuer_name == "Comercializadora Anidada SAS"
    assert doc.total == Decimal("357000.00")
    assert not doc.cufe.endswith("CONTENEDOR")


def test_xml_corrupto_lanza_malformed() -> None:
    with pytest.raises(MalformedUblError):
        parse_ubl(_load("corrupto.xml"))


def test_descuadre_de_totales_genera_warning() -> None:
    doc = parse_ubl(_load("factura_descuadrada.xml"))

    # No falla, pero marca el documento para revision.
    assert doc.total == Decimal("130000.00")
    assert doc.warnings
    assert "Descuadre" in doc.warnings[0]


def test_xxe_no_resuelve_entidades_externas() -> None:
    # No debe leer /etc/passwd: la entidad externa no se expande. Rechazar el
    # documento con MalformedUblError tambien es una defensa aceptable.
    try:
        doc = parse_ubl(_load("xxe.xml"))
    except MalformedUblError:
        return
    assert "root:" not in (doc.issuer_name or "")


def test_falta_cufe_lanza_error() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
             xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:ID>SIN-CUFE-1</cbc:ID>
      <cbc:IssueDate>2026-01-15</cbc:IssueDate>
    </Invoice>"""
    with pytest.raises(MissingCufeError):
        parse_ubl(xml)


def test_raiz_no_soportada_lanza_error() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <Pedido xmlns="urn:cualquier:otro:namespace">
      <id>123</id>
    </Pedido>"""
    with pytest.raises(UnsupportedDocumentTypeError):
        parse_ubl(xml)


# --- Fase C: moneda extranjera y nomina ---


def test_factura_moneda_extranjera_trae_trm() -> None:
    doc = parse_ubl(_load("factura_moneda_extranjera.xml"))

    assert doc.currency == "USD"
    assert doc.exchange_rate == Decimal("4000.00")
    # Los montos se guardan en la moneda original (la conversion ocurre al contabilizar).
    assert doc.subtotal == Decimal("100.00")
    assert doc.total_tax == Decimal("19.00")


def test_factura_cop_no_tiene_trm() -> None:
    doc = parse_ubl(_load("factura_simple.xml"))
    assert doc.currency == "COP"
    assert doc.exchange_rate is None


def test_nomina_ligera() -> None:
    doc = parse_ubl(_load("nomina_simple.xml"))

    assert doc.doc_type is DocType.NOMINA_ELECTRONICA
    assert len(doc.cufe) == 96  # CUNE
    assert doc.document_number == "NE0001"
    assert doc.issuer_nit == "900123456"  # empleador
    assert doc.issuer_name == "Empresa Empleadora SAS"
    assert doc.receiver_nit == "1098765432"  # trabajador
    assert doc.subtotal == Decimal("3000000.00")  # devengados
    assert doc.total_withholding == Decimal("240000.00")  # deducciones
    assert doc.total == Decimal("2760000.00")  # comprobante
    assert doc.total_tax == Decimal("0")
    assert not doc.taxes
    assert not doc.warnings  # devengados - deducciones == comprobante
