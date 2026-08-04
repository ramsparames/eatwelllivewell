import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import SYNAMATE_SECRET_WEBHOOK
from app.database import upsert_clarity_call_appointment


logger = logging.getLogger(__name__)

router = APIRouter()


def first_value(
    payload: dict[str, Any],
    *keys: str,
) -> Any:
    """
    Return the first non-empty value found among several possible keys.

    Synamate workflow payload field names can vary depending on how
    the outbound webhook is configured.
    """
    for key in keys:
        value = payload.get(key)

        if value not in (None, ""):
            return value

    return None


@router.post("/webhooks/synamate/calendar")
async def receive_synamate_calendar_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
):
    if not SYNAMATE_SECRET_WEBHOOK:
        raise HTTPException(
            status_code=500,
            detail="Webhook secret is not configured",
        )

    if x_webhook_secret != SYNAMATE_SECRET_WEBHOOK:
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook secret",
        )

    payload = await request.json()

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Webhook payload must be a JSON object",
        )

    external_appointment_id = first_value(
        payload,
        "appointmentId",
        "appointment_id",
        "id",
    )

    calendar_id = first_value(
        payload,
        "calendarId",
        "calendar_id",
    )

    start_time = first_value(
        payload,
        "startTime",
        "start_time",
        "appointmentStartTime",
    )

    if not external_appointment_id:
        raise HTTPException(
            status_code=400,
            detail="Appointment ID is missing",
        )

    if not calendar_id:
        raise HTTPException(
            status_code=400,
            detail="Calendar ID is missing",
        )

    if not start_time:
        raise HTTPException(
            status_code=400,
            detail="Appointment start time is missing",
        )

    # Ignore events belonging to another calendar.
    clarity_calendar_id = "IBwI80BhwMVqhD9qvMXF"

    if calendar_id != clarity_calendar_id:
        return {
            "status": "ignored",
            "reason": "Not the Clarity Call calendar",
        }

    contact = payload.get("contact")

    if not isinstance(contact, dict):
        contact = {}

    name = first_value(
        payload,
        "name",
        "contactName",
        "fullName",
    ) or first_value(
        contact,
        "name",
        "fullName",
    )

    email = first_value(
        payload,
        "email",
        "contactEmail",
    ) or first_value(
        contact,
        "email",
    )

    phone = first_value(
        payload,
        "phone",
        "contactPhone",
    ) or first_value(
        contact,
        "phone",
    )

    contact_id = first_value(
        payload,
        "contactId",
        "contact_id",
    ) or first_value(
        contact,
        "id",
        "contactId",
    )

    appointment_status = first_value(
        payload,
        "appointmentStatus",
        "status",
    )

    title = first_value(
        payload,
        "title",
        "appointmentTitle",
        "calendarName",
    ) or "Clarity Call with Sushma"

    meeting_location = first_value(
        payload,
        "meetingLocation",
        "meeting_location",
        "location",
        "meetingUrl",
        "meeting_url",
    )

    end_time = first_value(
        payload,
        "endTime",
        "end_time",
        "appointmentEndTime",
    )

    appointment_id = upsert_clarity_call_appointment(
        external_appointment_id=str(external_appointment_id),
        calendar_id=str(calendar_id),
        contact_id=str(contact_id) if contact_id else None,
        name=str(name) if name else None,
        email=str(email) if email else None,
        phone=str(phone) if phone else None,
        appointment_status=(
            str(appointment_status)
            if appointment_status
            else None
        ),
        title=str(title) if title else None,
        meeting_location=(
            str(meeting_location)
            if meeting_location
            else None
        ),
        start_time=str(start_time),
        end_time=str(end_time) if end_time else None,
        raw_payload=payload,
    )

    logger.info(
        "Synamate appointment saved: %s",
        external_appointment_id,
    )

    return {
        "status": "saved",
        "appointment_id": appointment_id,
    }
