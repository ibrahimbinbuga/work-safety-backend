# backend/routes/reports.py
"""Reporting endpoints: summary data + CSV/Excel exports."""
import io
import os
import smtplib
import ssl
from collections import defaultdict
from datetime import datetime, date, timedelta, time
from typing import List, Optional
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenData
from database import get_db
from dependencies import get_current_user, verify_company_access
from services.report_generator import generate_csv, generate_excel, VIOLATION_TYPE_LABELS, VIOLATION_TYPE_MODELS
import models

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# VIOLATION_TYPE_LABELS and VIOLATION_TYPE_MODELS imported from services.report_generator


async def _get_company(db: AsyncSession, company_code: str) -> models.Company:
    result = await db.execute(
        select(models.Company).where(
            func.upper(models.Company.code) == func.upper(company_code)
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _build_filters(
    company_id: int,
    from_date: Optional[date],
    to_date: Optional[date],
    violation_types: List[str],
    review_statuses: List[str],
):
    filters = [models.Violations.company_id == company_id]
    if from_date:
        filters.append(
            models.Violations.tarih_saat >= datetime.combine(from_date, time.min)
        )
    if to_date:
        filters.append(
            models.Violations.tarih_saat <= datetime.combine(to_date, time.max)
        )
    if violation_types:
        filters.append(models.Violations.ihlal_cesidi.in_(violation_types))
    if review_statuses:
        filters.append(models.Violations.review_status.in_(review_statuses))
    return filters


# ---------------------------------------------------------------------------
# Active violation types for a company (based on assigned models)
# ---------------------------------------------------------------------------

# Maps violation types to their model group label
_TYPE_TO_MODEL_GROUP = {
    "head":   "PPE Model",
    "vest":   "PPE Model",
    "fallen": "Fall Detection Model",
}


def _model_path_to_types(path: str) -> list[str]:
    """Infer applicable violation types from a model file path.

    Convention used in this project:
      - fall_model/... or any path containing 'fall' → Fall Detection
      - everything else                              → PPE (head + vest)
    """
    if "fall" in path.lower():
        return ["fallen"]
    return ["head", "vest"]


@router.get("/api/company/{company_code}/reports/active-types")
async def get_active_violation_types(
    company_code: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the violation types that are relevant for this company
    based on which models are currently assigned (is_active=True)."""
    await verify_company_access(current_user, company_code)
    company = await _get_company(db, company_code)

    result = await db.execute(
        select(models.ModelMeta)
        .join(models.CompanyModel, models.CompanyModel.model_id == models.ModelMeta.id)
        .where(
            models.CompanyModel.company_id == company.id,
            models.CompanyModel.is_active == True,
        )
    )
    assigned_models = result.scalars().all()

    active_types: list[str] = []
    for m in assigned_models:
        for t in _model_path_to_types(m.path or ""):
            if t not in active_types:
                active_types.append(t)

    # Fallback: if no models assigned yet, return all types so UI isn't empty
    if not active_types:
        active_types = ["head", "vest", "fallen"]

    return {
        "types": active_types,
        "groups": [
            {
                "label": group_label,
                "types": [t for t in active_types if _TYPE_TO_MODEL_GROUP.get(t) == group_label],
            }
            for group_label in dict.fromkeys(
                _TYPE_TO_MODEL_GROUP[t] for t in active_types if t in _TYPE_TO_MODEL_GROUP
            )
        ],
    }


# ---------------------------------------------------------------------------
# Report data endpoint
# ---------------------------------------------------------------------------

@router.get("/api/company/{company_code}/reports/data")
async def get_report_data(
    company_code: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    violation_types: List[str] = Query(default=[]),
    review_statuses: List[str] = Query(default=[]),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)
    company = await _get_company(db, company_code)

    filters = _build_filters(company.id, from_date, to_date, violation_types, review_statuses)

    result = await db.execute(
        select(models.Violations)
        .where(and_(*filters))
        .order_by(models.Violations.tarih_saat.asc())
    )
    violations = result.scalars().all()

    # --- aggregations ---
    by_type: dict[str, int] = defaultdict(int)
    by_status: dict[str, int] = defaultdict(int)
    by_camera: dict[str, int] = defaultdict(int)
    by_day: dict[str, int] = defaultdict(int)

    for v in violations:
        by_type[v.ihlal_cesidi] += 1
        by_status[v.review_status or "pending"] += 1
        cam_label = f"Camera {v.ihlal_yapilan_bolge}" if v.ihlal_yapilan_bolge else "Unknown"
        by_camera[cam_label] += 1
        if v.tarih_saat:
            day_key = v.tarih_saat.strftime("%Y-%m-%d")
            by_day[day_key] += 1

    # Top camera
    top_camera = max(by_camera, key=by_camera.get) if by_camera else "—"

    # Fill missing days in range so chart is continuous
    daily_data = []
    if from_date and to_date:
        current = from_date
        while current <= to_date:
            key = current.strftime("%Y-%m-%d")
            daily_data.append({
                "date": current.strftime("%b %d"),
                "full_date": key,
                "violations": by_day.get(key, 0),
            })
            current += timedelta(days=1)
    else:
        for key in sorted(by_day.keys()):
            dt = datetime.strptime(key, "%Y-%m-%d")
            daily_data.append({
                "date": dt.strftime("%b %d"),
                "full_date": key,
                "violations": by_day[key],
            })

    # Violation distribution for pie chart
    violation_distribution = [
        {
            "name": VIOLATION_TYPE_LABELS.get(t, t),
            "value": cnt,
            "type": t,
        }
        for t, cnt in sorted(by_type.items(), key=lambda x: -x[1])
    ]

    # Camera bar chart data
    camera_data = [
        {"camera": cam, "violations": cnt}
        for cam, cnt in sorted(by_camera.items(), key=lambda x: -x[1])[:10]
    ]

    return {
        "summary": {
            "total": len(violations),
            "by_type": dict(by_type),
            "by_status": dict(by_status),
            "top_camera": top_camera,
            "pending": by_status.get("pending", 0),
            "reviewed": by_status.get("reviewed", 0),
            "resolved": by_status.get("resolved", 0),
        },
        "daily_data": daily_data,
        "violation_distribution": violation_distribution,
        "camera_data": camera_data,
        "violations": [
            {
                "id": v.id,
                "type": v.ihlal_cesidi,
                "type_label": VIOLATION_TYPE_LABELS.get(v.ihlal_cesidi, v.ihlal_cesidi),
                "model": VIOLATION_TYPE_MODELS.get(v.ihlal_cesidi, "Unknown"),
                "camera_id": v.ihlal_yapilan_bolge,
                "camera_label": f"Camera {v.ihlal_yapilan_bolge}" if v.ihlal_yapilan_bolge else "Unknown",
                "datetime": v.tarih_saat.isoformat() if v.tarih_saat else None,
                "review_status": v.review_status or "pending",
                "worker_id": v.violation_id,
            }
            for v in reversed(violations)  # newest first
        ],
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@router.get("/api/company/{company_code}/reports/export/csv")
async def export_csv(
    company_code: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    violation_types: List[str] = Query(default=[]),
    review_statuses: List[str] = Query(default=[]),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)
    company = await _get_company(db, company_code)

    filters = _build_filters(company.id, from_date, to_date, violation_types, review_statuses)
    result = await db.execute(
        select(models.Violations)
        .where(and_(*filters))
        .order_by(models.Violations.tarih_saat.desc())
    )
    violations = result.scalars().all()

    today = date.today()
    csv_bytes = generate_csv(violations, company_code, from_date or today, to_date or today)
    filename = f"violations_{company_code}_{today.isoformat()}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

@router.get("/api/company/{company_code}/reports/export/excel")
async def export_excel(
    company_code: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    violation_types: List[str] = Query(default=[]),
    review_statuses: List[str] = Query(default=[]),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)
    company = await _get_company(db, company_code)

    filters = _build_filters(company.id, from_date, to_date, violation_types, review_statuses)
    result = await db.execute(
        select(models.Violations)
        .where(and_(*filters))
        .order_by(models.Violations.tarih_saat.desc())
    )
    violations = result.scalars().all()

    today = date.today()
    excel_bytes = generate_excel(
        violations, company_code, company.name, from_date or today, to_date or today
    )
    filename = f"violations_{company_code}_{today.isoformat()}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/company/{company_code}/reports/email-pdf")
async def email_report_pdf(
    company_code: str,
    recipient_email: str = Form(...),
    pdf_file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_company_access(current_user, company_code)
    company = await _get_company(db, company_code)

    if "@" not in recipient_email or "." not in recipient_email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid recipient email")

    pdf_bytes = await pdf_file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="PDF file is empty")
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF file is too large (max 10MB)")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "")

    if not smtp_host or not smtp_user or not smtp_password or not smtp_from:
        raise HTTPException(
            status_code=500,
            detail="SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM",
        )

    filename = f"violations_{company_code}_{date.today().isoformat()}.pdf"
    company_label = getattr(company, "name", company_code.upper())

    msg = EmailMessage()
    msg["Subject"] = f"Safety Violations Report - {company_label}"
    msg["From"] = smtp_from
    msg["To"] = recipient_email
    msg.set_content(
        "Hello,\n\n"
        f"Please find attached the safety violations report for {company_label}.\n\n"
        "Best regards,\n"
        "SafetyWatch"
    )
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")

    return {"message": f"Report emailed to {recipient_email}"}
