"""Tests de verify_xades: firma valida, manipulada y ausente (certificados de prueba)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner

from contaflow.ingestion.signature import verify_xades


def _cert_and_key(cn: str = "Proveedor Test SAS") -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return key_pem, cert_pem


def _signed_invoice(key_pem: bytes, cert_pem: bytes) -> bytes:
    root = etree.fromstring(
        b'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">'
        b"<ID>SETP-1</ID><IssuerName>Proveedor Test SAS</IssuerName></Invoice>"
    )
    signed = XMLSigner().sign(root, key=key_pem, cert=cert_pem)
    return etree.tostring(signed)


def test_firma_valida() -> None:
    key_pem, cert_pem = _cert_and_key()
    xml = _signed_invoice(key_pem, cert_pem)

    result = verify_xades(xml)
    assert result.present is True
    assert result.valid is True
    assert result.signer == "Proveedor Test SAS"
    assert result.trusted is False  # la confianza (cadena de CA) es de la Fase F


def test_firma_manipulada_invalida() -> None:
    key_pem, cert_pem = _cert_and_key()
    xml = _signed_invoice(key_pem, cert_pem)
    # Alteramos el contenido firmado: el digest deja de cuadrar.
    tampered = xml.replace(b"Proveedor Test SAS", b"Otro Proveedor XYZ")
    assert tampered != xml

    result = verify_xades(tampered)
    assert result.present is True
    assert result.valid is False


def test_sin_firma() -> None:
    result = verify_xades(b'<Invoice xmlns="urn:x"><ID>1</ID></Invoice>')
    assert result.present is False
    assert result.valid is False
