"""Tests de extraccion de adjuntos desde un correo (sin servidor IMAP real)."""

from __future__ import annotations

import io
import zipfile
from email.message import EmailMessage

import pytest

from contaflow.core.exceptions import AttachmentTooLargeError, ZipBombError
from contaflow.ingestion import imap_reader
from contaflow.ingestion.imap_reader import extract_xml_attachments

XML = b'<?xml version="1.0"?><Invoice>ejemplo</Invoice>'


def _email_with(attachments: list[tuple[bytes, str, str]]) -> bytes:
    msg = EmailMessage()
    msg["From"] = "proveedor@ejemplo.co"
    msg["To"] = "empresa@ejemplo.co"
    msg["Subject"] = "Factura electronica"
    msg.set_content("Adjuntamos su factura.")
    for data, subtype, filename in attachments:
        msg.add_attachment(data, maintype="application", subtype=subtype, filename=filename)
    return msg.as_bytes()


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_xml_directo() -> None:
    raw = _email_with([(XML, "xml", "factura.xml")])
    result = extract_xml_attachments(raw)
    assert len(result) == 1
    assert result[0][0] == "factura.xml"
    assert result[0][1] == XML


def test_xml_dentro_de_zip() -> None:
    zip_data = _zip_bytes({"factura.xml": XML, "factura.pdf": b"%PDF-1.4 ..."})
    raw = _email_with([(zip_data, "zip", "documentos.zip")])
    result = extract_xml_attachments(raw)
    assert len(result) == 1
    assert result[0][0] == "factura.xml"
    assert result[0][1] == XML


def test_ignora_adjuntos_no_xml() -> None:
    raw = _email_with([(b"%PDF-1.4", "pdf", "factura.pdf")])
    assert extract_xml_attachments(raw) == []


def test_zip_bomb_por_ratio() -> None:
    # 1 MB de ceros comprime a poquisimo: ratio muy por encima del limite.
    zip_data = _zip_bytes({"bomba.xml": b"0" * 1_000_000})
    raw = _email_with([(zip_data, "zip", "bomba.zip")])
    with pytest.raises(ZipBombError):
        extract_xml_attachments(raw)


def test_adjunto_xml_demasiado_grande(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imap_reader, "MAX_ATTACHMENT_BYTES", 16)
    raw = _email_with([(b"x" * 100, "xml", "grande.xml")])
    with pytest.raises(AttachmentTooLargeError):
        extract_xml_attachments(raw)
