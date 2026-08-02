import html
import logging
from typing import Any

import resend

from app.config import (
    APP_BASE_URL,
    COACH_NOTIFICATION_EMAIL,
    RESEND_API_KEY,
    RESEND_FROM_EMAIL,
)


logger = logging.getLogger(__name__)

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def _email_layout(
    *,
    title: str,
    intro: str,
    body: str,
    button_text: str,
    button_url: str,
) -> str:
    """Return a mobile-friendly NourisHer branded email."""

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{html.escape(title)}</title>
    </head>

    <body style="
        margin:0;
        padding:0;
        background:#f7f4f8;
        font-family:Arial,Helvetica,sans-serif;
        color:#2a2430;
    ">

        <div style="
            display:none;
            max-height:0;
            overflow:hidden;
            opacity:0;
        ">
            {html.escape(intro)}
        </div>

        <table
            role="presentation"
            width="100%"
            cellpadding="0"
            cellspacing="0"
            style="background:#f7f4f8;"
        >
            <tr>
                <td align="center" style="padding:30px 14px;">

                    <table
                        role="presentation"
                        width="100%"
                        cellpadding="0"
                        cellspacing="0"
                        style="
                            max-width:620px;
                            background:#ffffff;
                            border-radius:20px;
                            overflow:hidden;
                            box-shadow:0 12px 35px rgba(52,18,67,0.10);
                        "
                    >
                        <tr>
                            <td style="
                                padding:30px 34px;
                                background:
                                    linear-gradient(
                                        135deg,
                                        #3f0866,
                                        #5b0e91
                                    );
                            ">
                                <div style="
                                    color:#f5c518;
                                    font-size:11px;
                                    font-weight:700;
                                    letter-spacing:2px;
                                    text-transform:uppercase;
                                ">
                                    Eat Well Live Well
                                </div>

                                <h1 style="
                                    margin:9px 0 0;
                                    color:#ffffff;
                                    font-size:27px;
                                    line-height:1.25;
                                ">
                                    {html.escape(title)}
                                </h1>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:32px 34px 12px;">
                                <p style="
                                    margin:0;
                                    color:#5e5663;
                                    font-size:15px;
                                    line-height:1.7;
                                ">
                                    {html.escape(intro)}
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:12px 34px 28px;">
                                {body}
                            </td>
                        </tr>

                        <tr>
                            <td align="center" style="padding:0 34px 34px;">
                                <a
                                    href="{html.escape(button_url)}"
                                    style="
                                        display:inline-block;
                                        padding:14px 24px;
                                        border-radius:999px;
                                        color:#ffffff;
                                        background:#5b0e91;
                                        font-size:14px;
                                        font-weight:700;
                                        text-decoration:none;
                                    "
                                >
                                    {html.escape(button_text)} →
                                </a>
                            </td>
                        </tr>

                        <tr>
                            <td style="
                                padding:20px 34px;
                                border-top:1px solid #eee7f1;
                                color:#8a818e;
                                font-size:11px;
                                line-height:1.6;
                                text-align:center;
                            ">
                                NourisHer by Eat Well Live Well<br>
                                Personalised health coaching for women 35+
                            </td>
                        </tr>
                    </table>

                </td>
            </tr>
        </table>

    </body>
    </html>
    """


def _detail_row(label: str, value: Any) -> str:
    safe_label = html.escape(str(label))
    safe_value = html.escape(str(value if value is not None else "—"))

    return f"""
    <tr>
        <td style="
            width:42%;
            padding:11px 12px;
            border-bottom:1px solid #eee7f1;
            color:#766d79;
            font-size:12px;
            font-weight:700;
            vertical-align:top;
        ">
            {safe_label}
        </td>

        <td style="
            padding:11px 12px;
            border-bottom:1px solid #eee7f1;
            color:#2a2430;
            font-size:13px;
            font-weight:600;
            vertical-align:top;
        ">
            {safe_value}
        </td>
    </tr>
    """


def send_email(
    *,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> str | None:
    """
    Send an internal coach notification.

    A failure is logged but never prevents the public form from succeeding.
    """

    if not RESEND_API_KEY:
        logger.warning(
            "Email skipped: RESEND_API_KEY is not configured"
        )
        return None

    if not COACH_NOTIFICATION_EMAIL:
        logger.warning(
            "Email skipped: COACH_NOTIFICATION_EMAIL is not configured"
        )
        return None

    try:
        params: resend.Emails.SendParams = {
            "from": RESEND_FROM_EMAIL,
            "to": [COACH_NOTIFICATION_EMAIL],
            "subject": subject,
            "html": html_content,
        }

        if text_content:
            params["text"] = text_content

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
    result: dict[str, Any],
) -> str | None:
    clean_name = name.strip() or "New lead"
    total_score = result.get("total", "—")
    opportunity = str(
        result.get("opportunity", "Not available")
    ).replace("_", " ").title()
    strength = str(
        result.get("strength", "Not available")
    ).replace("_", " ").title()

    dashboard_url = (
        f"{APP_BASE_URL.rstrip('/')}"
        f"/dashboard/leads/assessment/{submission_id}"
    )

    body = f"""
    <div style="
        margin-bottom:18px;
        padding:18px;
        border-radius:15px;
        background:#f7effc;
        text-align:center;
    ">
        <div style="
            color:#5b0e91;
            font-size:42px;
            font-weight:800;
            line-height:1;
        ">
            {html.escape(str(total_score))}
        </div>

        <div style="
            margin-top:6px;
            color:#766d79;
            font-size:11px;
            font-weight:700;
            letter-spacing:1px;
            text-transform:uppercase;
        ">
            Overall assessment score
        </div>
    </div>

    <table
        role="presentation"
        width="100%"
        cellpadding="0"
        cellspacing="0"
        style="
            border:1px solid #eee7f1;
            border-radius:14px;
            border-collapse:separate;
            border-spacing:0;
            overflow:hidden;
        "
    >
        {_detail_row("Name", clean_name)}
        {_detail_row("Phone", phone)}
        {_detail_row("Biggest opportunity", opportunity)}
        {_detail_row("Strongest area", strength)}
        {_detail_row("Assessment ID", submission_id)}
    </table>
    """

    email_html = _email_layout(
        title="New NourisHer Assessment",
        intro=(
            f"{clean_name} has completed the NourisHer Assessment. "
            "Her personalised snapshot is ready for review."
        ),
        body=body,
        button_text="Open lead profile",
        button_url=dashboard_url,
    )

    text_content = (
        "New NourisHer Assessment\n\n"
        f"Name: {clean_name}\n"
        f"Phone: {phone}\n"
        f"Score: {total_score}/100\n"
        f"Biggest opportunity: {opportunity}\n"
        f"Strongest area: {strength}\n\n"
        f"Open lead profile: {dashboard_url}"
    )

    return send_email(
        subject=f"New NourisHer Assessment — {clean_name}",
        html_content=email_html,
        text_content=text_content,
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
    clean_name = name.strip() or "New applicant"

    dashboard_url = (
        f"{APP_BASE_URL.rstrip('/')}"
        f"/dashboard/leads/application/{application_id}"
    )

    safe_reason = html.escape(why_now).replace("\n", "<br>")

    body = f"""
    <div style="
        margin-bottom:18px;
        padding:17px 18px;
        border-left:4px solid #f5c518;
        border-radius:12px;
        background:#fffaf0;
    ">
        <div style="
            margin-bottom:7px;
            color:#725400;
            font-size:11px;
            font-weight:800;
            letter-spacing:1px;
            text-transform:uppercase;
        ">
            Why support now?
        </div>

        <div style="
            color:#3b343f;
            font-size:14px;
            line-height:1.7;
        ">
            {safe_reason}
        </div>
    </div>

    <table
        role="presentation"
        width="100%"
        cellpadding="0"
        cellspacing="0"
        style="
            border:1px solid #eee7f1;
            border-radius:14px;
            border-collapse:separate;
            border-spacing:0;
            overflow:hidden;
        "
    >
        {_detail_row("Name", clean_name)}
        {_detail_row("Email", email)}
        {_detail_row("Phone", phone)}
        {_detail_row("Age range", age_range)}
        {_detail_row("Application ID", application_id)}
    </table>
    """

    email_html = _email_layout(
        title="New Transformation Application",
        intro=(
            f"{clean_name} has applied for the NourisHer "
            "Transformation coaching experience."
        ),
        body=body,
        button_text="Review application",
        button_url=dashboard_url,
    )

    text_content = (
        "New Transformation Application\n\n"
        f"Name: {clean_name}\n"
        f"Email: {email}\n"
        f"Phone: {phone}\n"
        f"Age range: {age_range}\n"
        f"Why support now: {why_now}\n\n"
        f"Review application: {dashboard_url}"
    )

    return send_email(
        subject=f"New Transformation Application — {clean_name}",
        html_content=email_html,
        text_content=text_content,
    )
