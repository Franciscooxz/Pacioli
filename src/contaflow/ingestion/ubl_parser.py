"""Parser de facturas electronicas colombianas (UBL 2.1 / DIAN).

Expone `parse_ubl(xml_bytes) -> ParsedDocument`.

Seguridad: el XML se parsea con lxml SIN resolucion de entidades y sin red, para
evitar ataques XXE (lectura de archivos locales, SSRF) desde un adjunto malicioso.

Fidelidad: el parser refleja la naturaleza DIAN del documento (un <Invoice> normal es
FACTURA_VENTA). La perspectiva compra/venta se decide despues, en el pipeline, segun
el NIT de la empresa.

NOTA: las rutas UBL y algunos codigos (schemeName del CUFE, InvoiceTypeCode del
documento soporte) siguen la estructura estandar DIAN pero deben validarse contra
facturas reales anonimizadas. La validacion de la firma XAdES no se hace aqui (ver
PENDIENTES.md).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from lxml import etree

from contaflow.core.exceptions import (
    MalformedUblError,
    MissingCufeError,
    UnsupportedDocumentTypeError,
)
from contaflow.core.money import to_money
from contaflow.models.enums import DocType, TaxCategory
from contaflow.schemas.ubl import DocumentLine, ParsedDocument, TaxDetail

# Namespaces UBL 2.1 y la extension DIAN (sts).
NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
}

# Codigo InvoiceTypeCode que identifica un Documento Soporte (compras a no obligados).
_INVOICE_TYPE_DOCUMENTO_SOPORTE = {"05", "95"}

# Por raiz del XML: (tipo de documento, nombre del elemento de linea, elemento cantidad).
_LINE_CONFIG = {
    "Invoice": ("cac:InvoiceLine", "cbc:InvoicedQuantity"),
    "CreditNote": ("cac:CreditNoteLine", "cbc:CreditedQuantity"),
    "DebitNote": ("cac:DebitNoteLine", "cbc:DebitedQuantity"),
}

# Raices de nomina electronica (esquema propio, distinto a UBL de factura).
_NOMINA_ROOTS = {"NominaIndividual", "NominaIndividualDeAjuste"}

_MAX_UNNEST_DEPTH = 3


def _make_parser() -> etree.XMLParser:
    """Parser lxml endurecido contra XXE (sin entidades externas ni red)."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )


def _text(element: etree._Element, path: str) -> str | None:
    value = element.findtext(path, namespaces=NS)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _decimal(element: etree._Element, path: str, *, field: str) -> Decimal:
    raw = _text(element, path)
    if raw is None:
        raise MalformedUblError(f"Falta el importe requerido: {field} ({path})")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise MalformedUblError(f"Importe no numerico en {field}: {raw!r}") from exc


def _decimal_opt(element: etree._Element, path: str, default: str = "0") -> Decimal:
    raw = _text(element, path)
    if raw is None:
        return Decimal(default)
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise MalformedUblError(f"Importe no numerico en {path}: {raw!r}") from exc


def _resolve_doc_type(root_local: str, root: etree._Element) -> DocType:
    if root_local == "CreditNote":
        return DocType.NOTA_CREDITO
    if root_local == "DebitNote":
        return DocType.NOTA_DEBITO
    # Invoice: puede ser factura de venta o documento soporte, segun el codigo.
    type_code = _text(root, "cbc:InvoiceTypeCode")
    if type_code in _INVOICE_TYPE_DOCUMENTO_SOPORTE:
        return DocType.DOCUMENTO_SOPORTE
    return DocType.FACTURA_VENTA


def _tax_category(name: str, *, is_withholding: bool) -> TaxCategory:
    """Clasifica el impuesto por el nombre del esquema DIAN.

    NOTA: mapeo por nombre; validar contra XML reales (los codigos/nombres de esquema
    de la DIAN pueden variar). Ver PENDIENTES.md.
    """
    upper = name.upper()
    if is_withholding:
        if "FUENTE" in upper:
            return TaxCategory.RETEFUENTE
        if "IVA" in upper:
            return TaxCategory.RETEIVA
        if "ICA" in upper:
            return TaxCategory.RETEICA
        return TaxCategory.OTRO
    if "IVA" in upper:
        return TaxCategory.IVA
    return TaxCategory.OTRO


def _parse_tax_group(
    root: etree._Element, container_tag: str, *, is_withholding: bool
) -> tuple[list[TaxDetail], Decimal]:
    """Parsea un grupo de impuestos (cac:TaxTotal o cac:WithholdingTaxTotal)."""
    taxes: list[TaxDetail] = []
    total = Decimal("0")
    for container in root.findall(container_tag, namespaces=NS):
        total += _decimal_opt(container, "cbc:TaxAmount")
        for subtotal in container.findall("cac:TaxSubtotal", namespaces=NS):
            name = _text(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:Name") or "DESCONOCIDO"
            taxes.append(
                TaxDetail(
                    tax_name=name,
                    category=_tax_category(name, is_withholding=is_withholding),
                    is_withholding=is_withholding,
                    percent=_decimal_opt(subtotal, "cac:TaxCategory/cbc:Percent"),
                    taxable_amount=_decimal_opt(subtotal, "cbc:TaxableAmount"),
                    tax_amount=_decimal_opt(subtotal, "cbc:TaxAmount"),
                )
            )
    return taxes, total


def _parse_lines(root: etree._Element, root_local: str) -> list[DocumentLine]:
    line_tag, qty_tag = _LINE_CONFIG[root_local]
    lines: list[DocumentLine] = []
    for line in root.findall(line_tag, namespaces=NS):
        lines.append(
            DocumentLine(
                line_id=_text(line, "cbc:ID") or "",
                description=_text(line, "cac:Item/cbc:Description"),
                quantity=_decimal_opt(line, qty_tag),
                unit_price=_decimal_opt(line, "cac:Price/cbc:PriceAmount"),
                line_total=_decimal_opt(line, "cbc:LineExtensionAmount"),
            )
        )
    return lines


def _monetary_total(root: etree._Element, path: str, *, field: str) -> Decimal:
    """Lee un importe de LegalMonetaryTotal (o RequestedMonetaryTotal como respaldo)."""
    for container in ("cac:LegalMonetaryTotal", "cac:RequestedMonetaryTotal"):
        raw = _text(root, f"{container}/{path}")
        if raw is not None:
            try:
                return Decimal(raw)
            except InvalidOperation as exc:
                raise MalformedUblError(f"Importe no numerico en {field}: {raw!r}") from exc
    raise MalformedUblError(f"Falta el importe requerido: {field}")


def _monetary_total_opt(root: etree._Element, path: str) -> Decimal | None:
    """Como _monetary_total pero devuelve None si el importe no esta presente."""
    for container in ("cac:LegalMonetaryTotal", "cac:RequestedMonetaryTotal"):
        raw = _text(root, f"{container}/{path}")
        if raw is not None:
            try:
                return Decimal(raw)
            except InvalidOperation:
                return None
    return None


def _parse_document(root: etree._Element, root_local: str) -> ParsedDocument:
    cufe = _text(root, "cbc:UUID")
    if cufe is None:
        raise MissingCufeError("El documento no trae cbc:UUID (CUFE/CUDE).")

    document_number = _text(root, "cbc:ID")
    if document_number is None:
        raise MalformedUblError("Falta el numero de documento (cbc:ID).")

    issue_date = _text(root, "cbc:IssueDate")
    if issue_date is None:
        raise MalformedUblError("Falta la fecha de emision (cbc:IssueDate).")

    supplier = "cac:AccountingSupplierParty/cac:Party"
    customer = "cac:AccountingCustomerParty/cac:Party"
    issuer_nit = _text(root, f"{supplier}/cac:PartyTaxScheme/cbc:CompanyID")
    if issuer_nit is None:
        raise MalformedUblError("Falta el NIT del emisor.")
    issuer_name = _text(root, f"{supplier}/cac:PartyLegalEntity/cbc:RegistrationName") or _text(
        root, f"{supplier}/cac:PartyName/cbc:Name"
    )
    receiver_nit = _text(root, f"{customer}/cac:PartyTaxScheme/cbc:CompanyID")

    currency = _text(root, "cbc:DocumentCurrencyCode") or "COP"

    # TRM: solo relevante si la moneda no es COP. La DIAN puede traerla en el XML
    # (cac:PaymentExchangeRate/cbc:CalculationRate); si no viene, el posting la pedira
    # a un proveedor de TRM. Ver core/currency.py.
    exchange_rate: Decimal | None = None
    if currency != "COP":
        rate_raw = _text(root, "cac:PaymentExchangeRate/cbc:CalculationRate")
        if rate_raw is not None:
            try:
                exchange_rate = Decimal(rate_raw)
            except InvalidOperation as exc:
                raise MalformedUblError(f"TRM no numerica: {rate_raw!r}") from exc

    subtotal = _monetary_total(root, "cbc:LineExtensionAmount", field="subtotal")
    total = _monetary_total(root, "cbc:PayableAmount", field="total")
    taxes, total_tax = _parse_tax_group(root, "cac:TaxTotal", is_withholding=False)
    withholdings, total_withholding = _parse_tax_group(
        root, "cac:WithholdingTaxTotal", is_withholding=True
    )
    lines = _parse_lines(root, root_local)

    # El IVA debe cuadrar contra el total con impuestos (TaxInclusiveAmount); las
    # retenciones no entran aqui porque se aplican al pagar, no al total facturado.
    tax_inclusive = _monetary_total_opt(root, "cbc:TaxInclusiveAmount")
    reference = tax_inclusive if tax_inclusive is not None else total
    warnings: list[str] = []
    if to_money(subtotal) + to_money(total_tax) != to_money(reference):
        warnings.append(
            "Descuadre: subtotal + impuestos "
            f"({to_money(subtotal)} + {to_money(total_tax)}) != {to_money(reference)}."
        )

    return ParsedDocument(
        cufe=cufe,
        document_number=document_number,
        doc_type=_resolve_doc_type(root_local, root),
        issue_date=issue_date,  # Pydantic convierte 'YYYY-MM-DD' a date.
        issuer_nit=issuer_nit,
        issuer_name=issuer_name,
        receiver_nit=receiver_nit,
        currency=currency,
        exchange_rate=exchange_rate,
        subtotal=subtotal,
        total_tax=total_tax,
        total_withholding=total_withholding,
        total=total,
        taxes=taxes + withholdings,
        lines=lines,
        warnings=warnings,
    )


def _nomina_total(root: etree._Element, ns_uri: str, name: str) -> Decimal:
    """Lee un total de nomina como elemento <Name> o, si no, como atributo Name en la raiz."""
    element = root.find(f"{{{ns_uri}}}{name}")
    raw: str | None = None
    if element is not None and element.text:
        raw = element.text.strip()
    if raw is None:
        raw = root.get(name)
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _parse_nomina(root: etree._Element) -> ParsedDocument:
    """Parseo LIGERO de nomina electronica (NominaIndividual).

    Alcance aprobado: ingestar y guardar el documento como evidencia (CUNE, empleador,
    trabajador y totales devengados/deducciones/comprobante). NO es un modulo de nomina
    (CLAUDE.md seccion 8): no se contabiliza ni se liquida.

    VERIFICAR CONTRA XML REAL (regla 5): las rutas/atributos del esquema DIAN de nomina
    (InformacionGeneral@CUNE/@FechaGen/@TipoMoneda, Empleador@NIT, NumeroSecuenciaXML@Numero,
    y los totales) se asumen segun la estructura estandar; validar con una nomina real.
    Ver PENDIENTES.md.
    """
    ns_uri = etree.QName(root).namespace or ""

    def child(name: str) -> etree._Element | None:
        return root.find(f"{{{ns_uri}}}{name}")

    info = child("InformacionGeneral")
    empleador = child("Empleador")
    trabajador = child("Trabajador")
    secuencia = child("NumeroSecuenciaXML")

    cune = info.get("CUNE") if info is not None else None
    if not cune:
        raise MissingCufeError("La nomina no trae CUNE (InformacionGeneral@CUNE).")

    fecha = info.get("FechaGen") if info is not None else None
    if not fecha:
        raise MalformedUblError("Nomina sin fecha de generacion (InformacionGeneral@FechaGen).")

    nit = empleador.get("NIT") if empleador is not None else None
    if not nit:
        raise MalformedUblError("Nomina sin NIT del empleador (Empleador@NIT).")

    number = (secuencia.get("Numero") if secuencia is not None else None) or cune[:20]
    employer_name = empleador.get("RazonSocial") if empleador is not None else None
    worker_doc = trabajador.get("NumeroDocumento") if trabajador is not None else None
    currency = (info.get("TipoMoneda") if info is not None else None) or "COP"

    devengados = _nomina_total(root, ns_uri, "DevengadosTotal")
    deducciones = _nomina_total(root, ns_uri, "DeduccionesTotal")
    comprobante = _nomina_total(root, ns_uri, "ComprobanteTotal")

    warnings: list[str] = []
    if to_money(devengados) - to_money(deducciones) != to_money(comprobante):
        warnings.append(
            f"Descuadre nomina: devengados - deducciones ({to_money(devengados)} - "
            f"{to_money(deducciones)}) != {to_money(comprobante)}."
        )

    return ParsedDocument(
        cufe=cune,
        document_number=number,
        doc_type=DocType.NOMINA_ELECTRONICA,
        issue_date=fecha,  # Pydantic convierte 'YYYY-MM-DD' a date.
        issuer_nit=nit,
        issuer_name=employer_name,
        receiver_nit=worker_doc,
        currency=currency,
        subtotal=devengados,
        total_tax=Decimal("0"),
        total_withholding=deducciones,
        total=comprobante,
        taxes=[],
        lines=[],
        warnings=warnings,
    )


def _unnest_attached_document(root: etree._Element) -> bytes:
    """Extrae la factura real embebida como CDATA en un AttachedDocument."""
    description = _text(root, "cac:Attachment/cac:ExternalReference/cbc:Description")
    if description is None:
        raise MalformedUblError("AttachedDocument sin factura embebida (Description vacia).")
    return description.encode("utf-8")


def parse_ubl(xml_bytes: bytes, _depth: int = 0) -> ParsedDocument:
    """Parsea un XML UBL 2.1 (Invoice/CreditNote/DebitNote o AttachedDocument)."""
    if _depth > _MAX_UNNEST_DEPTH:
        raise MalformedUblError("Demasiados niveles de AttachedDocument anidados.")

    try:
        root = etree.fromstring(xml_bytes, parser=_make_parser())
    except etree.XMLSyntaxError as exc:
        raise MalformedUblError(f"XML invalido: {exc}") from exc

    root_local = etree.QName(root).localname

    if root_local == "AttachedDocument":
        return parse_ubl(_unnest_attached_document(root), _depth=_depth + 1)

    if root_local in _NOMINA_ROOTS:
        return _parse_nomina(root)

    if root_local not in _LINE_CONFIG:
        raise UnsupportedDocumentTypeError(f"Raiz no soportada: {root_local!r}")

    return _parse_document(root, root_local)
