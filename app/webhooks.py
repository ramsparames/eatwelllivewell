import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import SYNAMATE_SECRET_WEBHOOK
from app.database import upsert_clarity_call_appointment
from datetime import datetime
from zoneinfo import ZoneInfo

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
    
    calendar = payload.get("calendar")

    if not isinstance(calendar, dict):
        calendar = {}
        
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Webhook payload must be a JSON object",
        )

    external_appointment_id = first_value(
    calendar,
    "appointmentId",
    "appointment_id",
    )
    
    calendar_id = first_value(
        calendar,
        "id",
        "calendarId",
        "calendar_id",
    ) or "IBwI80BhwMVqhD9qvMXF"
    
    start_time = first_value(
        calendar,
        "startTime",
        "start_time",
    )
    
    end_time = first_value(
        calendar,
        "endTime",
        "end_time",
    )
    
    appointment_status = first_value(
        calendar,
        "appoinmentStatus",
        "appointmentStatus",
        "status",
    )
    
    title = first_value(
        calendar,
        "title",
        "calendarName",
    ) or "Clarity Call with Sushma"
    
    meeting_location = first_value(
        calendar,
        "address",
        "meetingLocation",
        "location",
    )
    
   # This workflow is already filtered to the Clarity Call calendar.
    calendar_id = "IBwI80BhwMVqhD9qvMXF"
    
    start_time = (
        first_value(
            payload,
            "startTime",
            "start_time",
            "appointmentStartTime",
        )
        or first_value(
            calendar,
            "startTime",
            "start_time",
            "start",
        )
    )
    
    end_time = (
        first_value(
            payload,
            "endTime",
            "end_time",
            "appointmentEndTime",
        )
        or first_value(
            calendar,
            "endTime",
            "end_time",
            "end",
        )
    )

    if not external_appointment_id:
        raise HTTPException(
        status_code=400,
        detail="Appointment ID is missing",
    )
    
    if not start_time:
       raise HTTPException(
        status_code=400,
       detail="Appointment start time is missing",    
    )
    
    # Some Synamate workflow payloads do not expose an appointment ID.
    # Create a stable fallback using the calendar, start time and contact.
    if not external_appointment_id:
        fallback_contact = (
            first_value(payload, "contactId", "contact_id")
            or first_value(
                payload.get("contact", {})
                if isinstance(payload.get("contact"), dict)
                else {},
                "id",
                "contactId",
            )
            or "unknown-contact"
        )

    external_appointment_id = (
        f"{calendar_id}:{start_time}:{fallback_contact}"
    )

    # Ignore events belonging to another calendar.
    clarity_calendar_id = "IBwI80BhwMVqhD9qvMXF"

    contact = payload.get("contact")

    if not isinstance(contact, dict):
        contact = {}

    contact_id = first_value(
    payload,
    "contact_id",
    "contactId",
    )
    
    name = first_value(
        payload,
        "full_name",
        "name",
    )
    
    email = first_value(
        payload,
        "email",
    )
    
    phone = first_value(
        payload,
        "phone",
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
    ist = ZoneInfo("Asia/Kolkata")

    start_dt = datetime.fromisoformat(str(start_time))
    
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=ist)
    
    start_time = start_dt.isoformat()
    
    if end_time:
        end_dt = datetime.fromisoformat(str(end_time))
    
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=ist)
    
    end_time = end_dt.isoformat()
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
