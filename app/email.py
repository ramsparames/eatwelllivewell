import html
import logging

import resend

from app.config import (
    COACH_NOTIFICATION_EMAIL,
    RESEND_API_KEY,
)


logger = logging.getLogger(__name__)


if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def send_email(
    *,
    subject: str,
    html_content: str,
) -> str | None:
    """
    Send an internal notification email to the coach.

    Email failure is logged but does not break the public form submission.
    """
    if not RESEND_API_KEY:
        logger.warning("Email skipped: RESEND_API_KEY is not configured")
        return None

    if not COACH_NOTIFICATION_EMAIL:
        logger.warning(
            "Email skipped: COACH_NOTIFICATION_EMAIL is not configured"
        )
        return None

    try:
        params: resend.Emails.SendParams = {
            "from": "NourisHer <onboarding@resend.dev>",
            "to": [COACH_NOTIFICATION_EMAIL],
            "subject": subject,
            "html": html_content,
        }

        response = resend.Emails.send(params)

        email_id = response.get("id") if response else None

        logger.info(
            "Notification email sent. Email ID: %s",
            email_id,
        )

        return email_id

    except Exception:
        logger.exception("Notification email could not be sent")
        return None


def send_assessment_notification(
    *,
    submission_id: int,
    name: str,
    phone: str,
    result: dict,
) -> str | None:
    safe_name = html.escape(name)
    safe_phone = html.escape(phone)
    safe_opportunity = html.escape(
        str(result.get("opportunity", "Not available"))
    )
    safe_strength = html.escape(
        str(result.get("strength", "Not available"))
    )
    total_score = result.get("total", "—")

    html_content = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#222;">
        <h2 style="color:#5B0E91;">
            New NourisHer Assessment
        </h2>

        <p>A new assessment has been completed.</p>

        <table cellpadding="8" cellspacing="0"
               style="border-collapse:collapse;">
            <tr>
                <td><strong>Name</strong></td>
                <td>{safe_name}</td>
            </tr>
            <tr>
                <td><strong>Phone</strong></td>
                <td>{safe_phone}</td>
            </tr>
            <tr>
                <td><strong>Total score</strong></td>
                <td>{total_score}/100</td>
            </tr>
            <tr>
                <td><strong>Biggest opportunity</strong></td>
                <td>{safe_opportunity}</td>
            </tr>
            <tr>
                <td><strong>Strongest area</strong></td>
                <td>{safe_strength}</td>
            </tr>
            <tr>
                <td><strong>Submission ID</strong></td>
                <td>{submission_id}</td>
            </tr>
        </table>

        <p style="margin-top:24px;">
            Sign in to the Coach Dashboard to view the complete assessment.
        </p>
    </div>
    """

    return send_email(
        subject=f"New NourisHer Assessment — {safe_name}",
        html_content=html_content,
    )


def send_application_notification(
    *,
    application_id: int,
    name: str,
    email: str,
    phone: str,
    age_range: str,
    why_now: str,
) -> str | None:
    safe_name = html.escape(name)
    safe_email = html.escape(email)
    safe_phone = html.escape(phone)
    safe_age = html.escape(age_range)
    safe_why_now = html.escape(why_now)

    html_content = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#222;">
        <h2 style="color:#5B0E91;">
            New Transformation Application
        </h2>

        <p>A new Transformation application has been submitted.</p>

        <table cellpadding="8" cellspacing="0"
               style="border-collapse:collapse;">
            <tr>
                <td><strong>Name</strong></td>
                <td>{safe_name}</td>
            </tr>
            <tr>
                <td><strong>Email</strong></td>
                <td>{safe_email}</td>
            </tr>
            <tr>
                <td><strong>Phone</strong></td>
                <td>{safe_phone}</td>
            </tr>
            <tr>
                <td><strong>Age range</strong></td>
                <td>{safe_age}</td>
            </tr>
            <tr>
                <td><strong>Application ID</strong></td>
                <td>{application_id}</td>
            </tr>
        </table>

        <h3 style="margin-top:24px;">Why support now?</h3>
        <p>{safe_why_now}</p>

        <p style="margin-top:24px;">
            Sign in to the Coach Dashboard to view the full application.
        </p>
    </div>
    """

    return send_email(
        subject=f"New Transformation Application — {safe_name}",
        html_content=html_content,
    )
