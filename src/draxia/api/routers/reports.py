"""Reportes contables: resumen agregado y exportacion CSV. Multi-tenant."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from draxia.api.deps import get_current_user
from draxia.db import get_async_session
from draxia.models.enums import DocumentStatus
from draxia.models.source_document import SourceDocument
from draxia.models.user import User
from draxia.schemas.report import MonthBucket, ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])

_ZERO = Decimal("0")


def _conds(
    user: User,
    company_id: uuid.UUID | None,
    status_filter: DocumentStatus | None,
    date_from: date | None,
    date_to: date | None,
) -> list[Any]:
    conds: list[Any] = [SourceDocument.tenant_id == user.tenant_id]
    if company_id is not None:
        conds.append(SourceDocument.company_id == company_id)
    if status_filter is not None:
        conds.append(SourceDocument.status == status_filter)
    if date_from is not None:
        conds.append(SourceDocument.issue_date >= date_from)
    if date_to is not None:
        conds.append(SourceDocument.issue_date <= date_to)
    return conds


@router.get("/summary", response_model=ReportSummary)
async def summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    company_id: uuid.UUID | None = Query(default=None),
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
) -> ReportSummary:
    conds = _conds(current_user, company_id, status_filter, date_from, date_to)

    totals = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(SourceDocument.subtotal), _ZERO),
                func.coalesce(func.sum(SourceDocument.total_tax), _ZERO),
                func.coalesce(func.sum(SourceDocument.total_withholding), _ZERO),
                func.coalesce(func.sum(SourceDocument.total), _ZERO),
            ).where(*conds)
        )
    ).one()

    by_status_rows = (
        await session.execute(
            select(SourceDocument.status, func.count())
            .where(*conds)
            .group_by(SourceDocument.status)
        )
    ).all()
    by_status = {status.value: count for status, count in by_status_rows}

    month_col = func.to_char(SourceDocument.issue_date, "YYYY-MM")
    month_rows = (
        await session.execute(
            select(month_col, func.count(), func.coalesce(func.sum(SourceDocument.total), _ZERO))
            .where(*conds, SourceDocument.issue_date.is_not(None))
            .group_by(month_col)
            .order_by(month_col)
        )
    ).all()
    by_month = [MonthBucket(month=m, count=c, total=t) for m, c, t in month_rows]

    return ReportSummary(
        count=totals[0],
        subtotal=totals[1],
        total_tax=totals[2],
        total_withholding=totals[3],
        total=totals[4],
        by_status=by_status,
        by_month=by_month,
    )


@router.get("/export.csv")
async def export_csv(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    company_id: uuid.UUID | None = Query(default=None),
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
) -> Response:
    conds = _conds(current_user, company_id, status_filter, date_from, date_to)
    docs = list(
        await session.scalars(
            select(SourceDocument).where(*conds).order_by(SourceDocument.issue_date)
        )
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "emisor",
            "nit",
            "tipo",
            "fecha",
            "moneda",
            "subtotal",
            "iva",
            "retenciones",
            "total",
            "estado",
        ]
    )
    for d in docs:
        writer.writerow(
            [
                d.issuer_name or "",
                d.issuer_nit or "",
                d.doc_type.value if d.doc_type else "",
                d.issue_date.isoformat() if d.issue_date else "",
                d.currency,
                str(d.subtotal) if d.subtotal is not None else "",
                str(d.total_tax) if d.total_tax is not None else "",
                str(d.total_withholding) if d.total_withholding is not None else "",
                str(d.total) if d.total is not None else "",
                d.status.value,
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documentos.csv"},
    )
