"""Excepciones tipadas del dominio.

Errores especificos en vez de un `except Exception` generico: quien llame al parser
debe poder distinguir "XML corrupto" de "falta el CUFE" de "tipo no soportado" para
decidir el estado del documento (PARSE_FAILED vs REJECTED, etc.).
"""

from __future__ import annotations


class DraxiaError(Exception):
    """Base de todas las excepciones propias del sistema."""


class UblParseError(DraxiaError):
    """Base de los errores de parseo de UBL."""


class MalformedUblError(UblParseError):
    """El XML no es valido o no tiene la estructura UBL esperada."""


class MissingCufeError(UblParseError):
    """El documento no trae CUFE/CUDE (cbc:UUID ausente o vacio)."""


class UnsupportedDocumentTypeError(UblParseError):
    """La raiz del XML no es un tipo de documento que sepamos parsear."""


class IngestionError(DraxiaError):
    """Base de los errores de ingesta (IMAP / adjuntos / almacenamiento)."""


class AttachmentTooLargeError(IngestionError):
    """Un adjunto supera el limite de tamano permitido."""


class ZipBombError(IngestionError):
    """Un ZIP se expande de forma sospechosa (posible zip bomb)."""


class PostingError(DraxiaError):
    """Error de datos/configuracion al armar o contabilizar un asiento (terminal)."""


class OdooConnectionError(DraxiaError):
    """Fallo transitorio hablando con Odoo (reintentar)."""
