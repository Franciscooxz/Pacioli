"""Cliente de Odoo via XML-RPC.

Regla del CLAUDE.md: contra Odoo SIEMPRE por su API (execute_kw), nunca SQL directo.
La interfaz OdooClient permite inyectar un doble en tests; XmlRpcOdooClient es la
implementacion real.

VERIFICAR CONTRA UN ODOO REAL (rule #5): las firmas y nombres de campos de Odoo 17
(account.move, account.account, res.partner, account.journal) siguen el modelo estandar,
pero conviene confirmarlos contra la instancia real y con l10n_co instalado. Ver
PENDIENTES.md.
"""

from __future__ import annotations

import xmlrpc.client
from typing import Any, Protocol, runtime_checkable

from contaflow.core.exceptions import OdooConnectionError


@runtime_checkable
class OdooClient(Protocol):
    """Operaciones que el posting necesita de Odoo."""

    def find_move_by_ref(self, ref: str) -> int | None: ...
    def find_account_id(self, code: str) -> int | None: ...
    def find_partner_id(self, nit: str) -> int | None: ...
    def create_partner(self, name: str, nit: str) -> int: ...
    def find_purchase_journal_id(self) -> int | None: ...
    def find_sale_journal_id(self) -> int | None: ...
    def create_move(self, move: dict[str, Any]) -> int: ...
    def post_move(self, move_id: int) -> None: ...


class XmlRpcOdooClient:
    """Implementacion real sobre xmlrpc. Un cliente por empresa (sus credenciales)."""

    def __init__(self, url: str, db: str, username: str, password: str) -> None:
        self._db = db
        self._password = password
        try:
            common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
            uid = common.authenticate(db, username, password, {})
        except (OSError, xmlrpc.client.Fault) as exc:
            raise OdooConnectionError(f"No se pudo autenticar contra Odoo: {exc}") from exc
        # authenticate devuelve el uid (int) o False si las credenciales fallan.
        if not isinstance(uid, int) or isinstance(uid, bool):
            raise OdooConnectionError("Odoo rechazo las credenciales")
        self._uid = uid
        self._models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def _execute(self, model: str, method: str, *args: Any) -> Any:
        try:
            return self._models.execute_kw(
                self._db, self._uid, self._password, model, method, list(args)
            )
        except (OSError, xmlrpc.client.Fault) as exc:
            raise OdooConnectionError(f"Fallo execute_kw {model}.{method}: {exc}") from exc

    def _search_one(self, model: str, domain: list[Any]) -> int | None:
        ids = self._execute(model, "search", domain, {"limit": 1})
        return int(ids[0]) if ids else None

    def find_move_by_ref(self, ref: str) -> int | None:
        return self._search_one("account.move", [["ref", "=", ref]])

    def find_account_id(self, code: str) -> int | None:
        return self._search_one("account.account", [["code", "=", code]])

    def find_partner_id(self, nit: str) -> int | None:
        return self._search_one("res.partner", [["vat", "=", nit]])

    def create_partner(self, name: str, nit: str) -> int:
        return int(self._execute("res.partner", "create", {"name": name, "vat": nit}))

    def find_purchase_journal_id(self) -> int | None:
        return self._search_one("account.journal", [["type", "=", "purchase"]])

    def find_sale_journal_id(self) -> int | None:
        return self._search_one("account.journal", [["type", "=", "sale"]])

    def create_move(self, move: dict[str, Any]) -> int:
        return int(self._execute("account.move", "create", move))

    def post_move(self, move_id: int) -> None:
        self._execute("account.move", "action_post", [move_id])
