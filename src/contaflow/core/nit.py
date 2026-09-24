"""Comparacion de NITs colombianos tolerando el digito de verificacion.

El NIT puede venir con o sin el digito de verificacion (900123456 vs 900123456-7) y con
separadores. Normalizamos a solo digitos y comparamos aceptando que uno traiga el DV y el
otro no. Se usa para decidir la perspectiva de un documento (compra vs venta) comparando
el NIT de la empresa con el emisor/receptor.
"""

from __future__ import annotations


def nit_digits(nit: str | None) -> str:
    """Devuelve solo los digitos de un NIT (sin puntos, guiones ni espacios)."""
    return "".join(c for c in (nit or "") if c.isdigit())


def same_nit(a: str | None, b: str | None) -> bool:
    """True si a y b son el mismo NIT, tolerando el digito de verificacion."""
    da, db = nit_digits(a), nit_digits(b)
    if not da or not db:
        return False
    return da == db or da[:-1] == db or da == db[:-1]
