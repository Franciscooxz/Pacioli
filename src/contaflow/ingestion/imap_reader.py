"""Lectura de buzones IMAP y extraccion de adjuntos XML (directos o dentro de ZIP).

El proveedor esta obligado a enviar la factura al correo del adquiriente con el XML
adjunto: esta es la via de ingesta principal. La interfaz Mailbox permite inyectar un
doble en tests sin levantar un servidor IMAP real.

Seguridad: no se loguea nunca el contenido del XML ni la direccion de correo completa.
Se aplican limites de tamano y guardas anti zip-bomb.
"""

from __future__ import annotations

import email
import imaplib
import io
import ssl
import zipfile
from collections.abc import Iterator
from email.policy import default as default_policy
from typing import Protocol, runtime_checkable

from contaflow.core.exceptions import AttachmentTooLargeError, ZipBombError

# Limite por adjunto (comprimido y descomprimido, cada archivo).
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
# Guardas anti zip-bomb.
MAX_ZIP_ENTRIES = 50
MAX_TOTAL_UNCOMPRESSED_BYTES = 60 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


@runtime_checkable
class Mailbox(Protocol):
    """Contrato minimo de un buzon de correo."""

    def search_unseen(self) -> list[str]:
        """UIDs de los correos no leidos."""
        ...

    def fetch(self, uid: str) -> bytes:
        """Correo completo (RFC822) por UID."""
        ...

    def mark_seen(self, uid: str) -> None:
        """Marca el correo como leido (solo tras persistir su contenido)."""
        ...

    def close(self) -> None:
        """Cierra la conexion."""
        ...


class ImapMailbox:
    """Implementacion de Mailbox sobre imaplib.IMAP4_SSL."""

    def __init__(
        self, host: str, port: int, username: str, password: str, folder: str = "INBOX"
    ) -> None:
        # Contexto TLS que verifica certificado y hostname (explicito, no confiar en
        # el default). Evita conectarse a un servidor IMAP suplantado.
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        self._conn = imaplib.IMAP4_SSL(host, port, ssl_context=context)
        self._conn.login(username, password)
        self._conn.select(folder)

    def search_unseen(self) -> list[str]:
        typ, data = self._conn.uid("search", "UNSEEN")
        if typ != "OK" or not data or data[0] is None:
            return []
        return [uid.decode("ascii") for uid in data[0].split()]

    def fetch(self, uid: str) -> bytes:
        typ, data = self._conn.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            raise OSError(f"No se pudo descargar el correo uid={uid}")
        payload = data[0][1]
        return bytes(payload)

    def mark_seen(self, uid: str) -> None:
        self._conn.uid("store", uid, "+FLAGS", "(\\Seen)")

    def close(self) -> None:
        try:
            self._conn.close()
        finally:
            self._conn.logout()


def _read_zip(data: bytes) -> Iterator[tuple[str, bytes]]:
    """Extrae los .xml de un ZIP aplicando guardas anti zip-bomb."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ZipBombError(f"ZIP con demasiadas entradas: {len(infos)}")
        total = 0
        for info in infos:
            if not info.filename.lower().endswith(".xml"):
                continue
            if info.file_size > MAX_ATTACHMENT_BYTES:
                raise AttachmentTooLargeError(f"Entrada ZIP demasiado grande: {info.file_size} B")
            if (
                info.compress_size > 0
                and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ZipBombError("Ratio de compresion sospechoso en el ZIP")
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise ZipBombError("El ZIP se expande por encima del limite total")
            with archive.open(info) as handle:
                content = handle.read(MAX_ATTACHMENT_BYTES + 1)
            if len(content) > MAX_ATTACHMENT_BYTES:
                raise AttachmentTooLargeError("Entrada ZIP demasiado grande al descomprimir")
            yield info.filename, content


def extract_xml_attachments(raw_email: bytes) -> list[tuple[str, bytes]]:
    """Devuelve [(nombre, xml_bytes)] de un correo: XML directos y XML dentro de ZIP."""
    message = email.message_from_bytes(raw_email, policy=default_policy)
    results: list[tuple[str, bytes]] = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, (bytes, bytearray)):
            continue
        data = bytes(payload)
        lower = filename.lower()
        if lower.endswith(".xml"):
            if len(data) > MAX_ATTACHMENT_BYTES:
                raise AttachmentTooLargeError(f"Adjunto XML demasiado grande: {len(data)} B")
            results.append((filename, data))
        elif lower.endswith(".zip"):
            if len(data) > MAX_ATTACHMENT_BYTES:
                raise AttachmentTooLargeError(f"Adjunto ZIP demasiado grande: {len(data)} B")
            results.extend(_read_zip(data))
    return results
