import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import SYNAMATE_SECRET_WEBHOOK, RAZORPAY_WEBHOOK_SECRET
from app.database import upsert_clarity_call_appointment, mark_transformation_interest_paid
from app.transformation_interest import qualify_transformation_interest_if_ready
from app.synamate import get_synamate_contact


logger = logging.getLogger(__name__)

router = APIRouter()

CLARITY_CALENDAR_ID = "IBwI80BhwMVqhD9qvMXF"
IST = ZoneInfo("Asia/Kolkata")


def first_value(
    payload: dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        value = payload.get(key)

        if value not in (None, ""):
            return value

    return None


def add_timezone(value: str | None) -> str | None:
    if not value:
        return None

    parsed = datetime.fromisoformat(str(value))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)

    return parsed.isoformat()


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

    calendar = payload.get("calendar")

    if not isinstance(calendar, dict):
        calendar = {}

    custom_data = payload.get("customData")

    if not isinstance(custom_data, dict):
        custom_data = {}

    external_appointment_id = (
        first_value(
            calendar,
            "appointmentId",
            "appointment_id",
        )
        or first_value(
            custom_data,
            "appointmentId",
            "appointment_id",
        )
    )

    start_time = (
        first_value(
            calendar,
            "startTime",
            "start_time",
        )
        or first_value(
            custom_data,
            "startTime",
            "start_time",
        )
    )

    end_time = (
        first_value(
            calendar,
            "endTime",
            "end_time",
        )
        or first_value(
            custom_data,
            "endTime",
            "end_time",
        )
    )

    if not start_time:
        raise HTTPException(
            status_code=400,
            detail="Appointment start time is missing",
        )

    contact_id = first_value(
        payload,
        "contact_id",
        "contactId",
    ) or first_value(
        custom_data,
        "contactId",
        "contact_id",
    )

    if not external_appointment_id:
        external_appointment_id = (
            f"{CLARITY_CALENDAR_ID}:"
            f"{start_time}:"
            f"{contact_id or 'unknown-contact'}"
        )

    name = (
        first_value(
            payload,
            "full_name",
            "name",
        )
        or first_value(
            custom_data,
            "name",
            "full_name",
        )
    )

    email = first_value(
        payload,
        "email",
    ) or first_value(
        custom_data,
        "email",
    )

    phone = first_value(
        payload,
        "phone",
    ) or first_value(
        custom_data,
        "phone",
    )

    # Some Synamate calendar webhooks include only contactId and omit the
    # contact's phone/name/email. Resolve the contact so the booking can be
    # matched back to the paid Transformation interest.
    if contact_id and (not phone or not name or not email):
        contact = get_synamate_contact(str(contact_id)) or {}
        phone = phone or contact.get("phone")
        email = email or contact.get("email")
        name = name or contact.get("name") or " ".join(
            part for part in [contact.get("firstName"), contact.get("lastName")] if part
        ).strip() or None

    appointment_status = (
        first_value(
            calendar,
            "appoinmentStatus",
            "appointmentStatus",
            "status",
        )
        or first_value(
            custom_data,
            "appointmentStatus",
            "status",
        )
    )

    title = (
        first_value(
            calendar,
            "title",
            "calendarName",
        )
        or "Clarity Call with Sushma"
    )

    meeting_location = (
        first_value(
            calendar,
            "address",
            "meetingLocation",
            "location",
        )
        or first_value(
            custom_data,
            "meetingLocation",
            "meeting_url",
        )
    )

    start_time = add_timezone(str(start_time))
    end_time = add_timezone(
        str(end_time) if end_time else None
    )

    appointment_id = upsert_clarity_call_appointment(
        external_appointment_id=str(
            external_appointment_id
        ),
        calendar_id=CLARITY_CALENDAR_ID,
        contact_id=(
            str(contact_id)
            if contact_id
            else None
        ),
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
        end_time=(
            str(end_time)
            if end_time
            else None
        ),
        raw_payload=payload,
    )

    logger.info(
        "Synamate appointment saved: %s",
        external_appointment_id,
    )

    if phone:
        qualify_transformation_interest_if_ready(phone=str(phone))

    return {
        "status": "saved",
        "appointment_id": appointment_id,
    }


@router.post("/webhooks/razorpay")
async def receive_razorpay_webhook(request: Request):
    import hashlib
    import hmac

    if not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay webhook secret is not configured")

    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")

    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    payload = await request.json()
    event = payload.get("event")
    if event not in {"payment_link.paid", "payment.captured"}:
        return {"status": "ignored"}

    payment_link_entity = ((payload.get("payload") or {}).get("payment_link") or {}).get("entity") or {}
    payment_entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}

    payment_link_id = payment_link_entity.get("id")
    reference_id = payment_link_entity.get("reference_id")
    payment_id = payment_entity.get("id")
    amount = payment_entity.get("amount") or payment_link_entity.get("amount_paid")

    updated = mark_transformation_interest_paid(
        payment_link_id=str(payment_link_id) if payment_link_id else None,
        reference_id=str(reference_id) if reference_id else None,
        payment_id=str(payment_id) if payment_id else None,
        amount=int(amount) if amount else None,
    )
    if updated:
        qualify_transformation_interest_if_ready(interest_id=updated)

    return {"status": "processed" if updated else "unmatched"}
