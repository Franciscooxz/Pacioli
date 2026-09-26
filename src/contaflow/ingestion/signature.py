"""Validacion de la firma digital de la factura electronica DIAN (XAdES-EPES).

Alcance de este modulo (Fase D):
- Verifica INTEGRIDAD y AUTENTICIDAD relativa: que el documento no fue alterado despues
  de firmarse y que la firma corresponde al certificado incrustado (recalculo de digests
  de las referencias + verificacion del valor de la firma, via signxml).
- Extrae los datos del certificado firmante (sujeto y vigencia).

DIFERIDO a la Fase F (necesita insumos externos):
- Validar que el certificado encadena a una CA raiz ACREDITADA en Colombia (ONAC).
- Validar el sello de tiempo y la politica de firma EPES.
Por eso el resultado marca `trusted=False` con una advertencia: hoy probamos integridad,
no la confianza en la identidad legal del firmante.

VERIFICAR contra XML DIAN reales: la firma se prueba hoy con certificados autofirmados
(fixtures sinteticos). La firma real vive en ext:UBLExtensions; aqui se busca en cualquier
parte del arbol para ser tolerantes. Ver PENDIENTES.md.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from lxml import etree

logger = logging.getLogger(__name__)

DS_NS = "http://www.w3.org/2000/09/xmldsig#"


@dataclass
class SignatureResult:
    """Resultado de validar la firma de un documento."""

    present: bool
    valid: bool  # integridad + la firma coincide con el certificado incrustado
    trusted: bool = False  # cadena a CA acreditada: se valida en la Fase F (hoy False)
    signer: str | None = None
    not_after: datetime | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _make_parser() -> etree.XMLParser:
    """Parser endurecido contra XXE (sin entidades externas ni red)."""
    return etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
    )


def _extract_cert(sig: etree._Element) -> x509.Certificate | None:
    node = sig.find(f".//{{{DS_NS}}}X509Certificate")
    if node is None or not node.text:
        return None
    der = base64.b64decode("".join(node.text.split()))
    return x509.load_der_x509_certificate(der)


def _signer_name(cert: x509.Certificate) -> str:
    cns = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if cns:
        value = cns[0].value
        return value if isinstance(value, str) else value.decode("utf-8", "replace")
    return cert.subject.rfc4514_string()


def verify_xades(xml_bytes: bytes) -> SignatureResult:
    """Valida la firma de un documento UBL/DIAN. Nunca lanza: devuelve el resultado."""
    # import local: dependencia pesada. signxml re-exporta XMLVerifier en runtime pero
    # mypy strict lo marca por su regla de re-export explicito.
    from signxml import XMLVerifier  # type: ignore[attr-defined]

    try:
        root = etree.fromstring(xml_bytes, parser=_make_parser())
    except etree.XMLSyntaxError as exc:
        return SignatureResult(present=False, valid=False, errors=[f"XML invalido: {exc}"])

    sig = root.find(f".//{{{DS_NS}}}Signature")
    if sig is None:
        return SignatureResult(
            present=False,
            valid=False,
            warnings=["El documento no trae firma digital (ds:Signature)."],
        )

    result = SignatureResult(present=True, valid=False)
    result.warnings.append(
        "Cadena de CA no verificada (Fase F): se prueba integridad, no la confianza legal."
    )

    cert: x509.Certificate | None = None
    try:
        cert = _extract_cert(sig)
    except Exception as exc:  # noqa: BLE001 - certificado ilegible
        result.errors.append(f"No se pudo leer el certificado firmante: {exc}")
    if cert is not None:
        result.signer = _signer_name(cert)
        result.not_after = cert.not_valid_after_utc

    try:
        cert_pem = cert.public_bytes(Encoding.PEM).decode() if cert is not None else None
        XMLVerifier().verify(xml_bytes, x509_cert=cert_pem)
        result.valid = True
    except Exception as exc:  # noqa: BLE001 - cualquier fallo cripto = firma no valida
        result.valid = False
        result.errors.append(f"Firma no valida: {type(exc).__name__}: {exc}")
    return result
