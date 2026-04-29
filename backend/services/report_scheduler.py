"""Scheduled automatic report emailer.

Three separate jobs, each fired at period-end:
  - Daily   → every day at 23:00 UTC      (covers today)
  - Weekly  → every Friday at 23:00 UTC   (covers Mon–Fri of the current week)
  - Monthly → last day of month 23:00 UTC (covers 1st – last day of month)
"""
import os
import smtplib
import ssl
from datetime import datetime, date, timedelta, time
from email.message import EmailMessage

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import AsyncSessionLocal
from services.report_generator import generate_csv, generate_excel, generate_pdf


# ---------------------------------------------------------------------------
# Date ranges
# ---------------------------------------------------------------------------

def _date_range_for_period(period: str):
    """Return (from_date, to_date) covering the period that just ended."""
    today = date.today()
    if period == "daily":
        # Full current day
        return today, today
    if period == "weekly":
        # Monday → Friday (current week)
        monday = today - timedelta(days=today.weekday())  # weekday() == 4 (Fri) when job runs
        return monday, today
    # monthly: 1st → last day of current month
    return today.replace(day=1), today


# ---------------------------------------------------------------------------
# Core sender (reusable for all periods)
# ---------------------------------------------------------------------------

async def _send_reports_for_period(period: str):
    period_label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[period]
    print(f"[Scheduler] Running {period_label} report job at {datetime.utcnow().isoformat()}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(models.CompanyNotificationSettings)
            .where(
                models.CompanyNotificationSettings.email_enabled == True,
                models.CompanyNotificationSettings.report_period == period,
            )
        )
        all_settings = result.scalars().all()

        if not all_settings:
            print(f"[Scheduler] No companies configured for {period_label} reports, skipping.")
            return

        from_date, to_date = _date_range_for_period(period)

        for ns in all_settings:
            company = await db.get(models.Company, ns.company_id)
            if not company:
                continue

            users_result = await db.execute(
                select(models.User).where(
                    models.User.company_id == ns.company_id,
                    models.User.is_active == True,
                )
            )
            recipients = [u.email for u in users_result.scalars().all()]
            if not recipients:
                print(f"[Scheduler] No active users for {company.code}, skipping")
                continue

            violations = await _fetch_violations(db, ns.company_id, from_date, to_date)
            formats = ns.report_formats or ["pdf"]
            attachments = []

            if "csv" in formats:
                attachments.append((
                    f"violations_{company.code}_{to_date}.csv",
                    generate_csv(violations, company.code, from_date, to_date),
                    "text", "csv",
                ))
            if "excel" in formats:
                attachments.append((
                    f"violations_{company.code}_{to_date}.xlsx",
                    generate_excel(violations, company.code, company.name, from_date, to_date),
                    "application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ))
            if "pdf" in formats:
                attachments.append((
                    f"violations_{company.code}_{to_date}.pdf",
                    generate_pdf(violations, company.code, company.name, from_date, to_date),
                    "application", "pdf",
                ))

            subject = f"SafetyWatch {period_label} Report – {company.code}"
            body = (
                f"Hello,\n\n"
                f"Please find attached the {period_label.lower()} safety violations report "
                f"for {company.name} ({company.code}).\n"
                f"Period: {from_date} → {to_date}\n"
                f"Total violations: {len(violations)}\n\n"
                f"Best regards,\nSafetyWatch"
            )

            try:
                _send_email(recipients, subject, body, attachments)
                print(f"[Scheduler] Sent {period_label} report for {company.code} to {recipients}")
            except Exception as exc:
                print(f"[Scheduler] Failed to send report for {company.code}: {exc}")


# ---------------------------------------------------------------------------
# Public job functions (called by APScheduler)
# ---------------------------------------------------------------------------

async def send_daily_reports():
    await _send_reports_for_period("daily")


async def send_weekly_reports():
    await _send_reports_for_period("weekly")


async def send_monthly_reports():
    await _send_reports_for_period("monthly")


# Legacy: still usable from test endpoint
async def send_scheduled_reports():
    """Trigger all three periods at once (used for manual testing)."""
    await _send_reports_for_period("daily")
    await _send_reports_for_period("weekly")
    await _send_reports_for_period("monthly")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_violations(db: AsyncSession, company_id: int, from_date: date, to_date: date):
    result = await db.execute(
        select(models.Violations)
        .where(
            and_(
                models.Violations.company_id == company_id,
                models.Violations.tarih_saat >= datetime.combine(from_date, time.min),
                models.Violations.tarih_saat <= datetime.combine(to_date, time.max),
            )
        )
        .order_by(models.Violations.tarih_saat.desc())
    )
    return result.scalars().all()


def _send_email(to_addresses: list[str], subject: str, body: str, attachments: list[tuple]):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user:
        print("[Scheduler] SMTP not configured – skipping email")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)

    for filename, data, mime_main, mime_sub in attachments:
        msg.add_attachment(data, maintype=mime_main, subtype=mime_sub, filename=filename)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
