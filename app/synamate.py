import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import (
    SYNAMATE_API_TOKEN,
    SYNAMATE_LOCATION_ID,
)


logger = logging.getLogger(__name__)

SYNAMATE_BASE_URL = "https://services.leadconnectorhq.com"


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)

    first_name = parts[0] if parts else "Lead"
    last_name = parts[1] if len(parts) > 1 else ""

    return first_name, last_name


def sync_transformation_applicant(
    *,
    application_id: int,
    name: str,
    email: str,
    phone: str,
) -> str | None:
    """
    Create or update a Synamate contact.

    Failure is logged but does not prevent the application from saving.
    """

    if not SYNAMATE_API_TOKEN:
        logger.warning(
            "Synamate sync skipped: SYNAMATE_API_TOKEN is missing"
        )
        return None

    if not SYNAMATE_LOCATION_ID:
        logger.warning(
            "Synamate sync skipped: SYNAMATE_LOCATION_ID is missing"
        )
        return None

    first_name, last_name = split_name(name)

    payload = {
        "locationId": SYNAMATE_LOCATION_ID,
        "firstName": first_name,
        "lastName": last_name,
        "email": email.strip().lower(),
        "phone": phone.strip(),
        "source": "NourisHer Transformation Application",
        "tags": [
            "Transformation Applicant",
            f"NourisHer Application {application_id}",
        ],
    }

    headers = {
        "Authorization": f"Bearer {SYNAMATE_API_TOKEN}",
        "Version": "2021-04-15",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            f"{SYNAMATE_BASE_URL}/contacts/upsert",
            json=payload,
            headers=headers,
            timeout=15.0,
        )

        response.raise_for_status()

        data = response.json()
        contact = data.get("contact") or {}
        contact_id = contact.get("id")

        logger.info(
            "Synamate contact synced. Contact ID: %s",
            contact_id,
        )

        return contact_id

    except httpx.HTTPStatusError as error:
        logger.error(
            "Synamate sync failed with status %s: %s",
            error.response.status_code,
            error.response.text,
        )
        return None

    except Exception:
        logger.exception("Synamate contact sync failed")
        return None


def get_synamate_contact(contact_id: str) -> dict | None:
    """Fetch one Synamate contact so webhook bookings can be matched reliably."""
    if not contact_id or not SYNAMATE_API_TOKEN:
        return None

    headers = {
        "Authorization": f"Bearer {SYNAMATE_API_TOKEN}",
        "Version": "2021-04-15",
        "Accept": "application/json",
    }

    try:
        response = httpx.get(
            f"{SYNAMATE_BASE_URL}/contacts/{contact_id}",
            headers=headers,
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        contact = data.get("contact") if isinstance(data, dict) else None
        return contact if isinstance(contact, dict) else None
    except Exception:
        logger.exception("Synamate contact lookup failed for %s", contact_id)
        return None


def _phone_digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _phones_match(left: str | None, right: str | None) -> bool:
    a = _phone_digits(left)
    b = _phone_digits(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 10 and len(b) >= 10 and a[-10:] == b[-10:]


def get_synamate_calendar_events(
    calendar_id: str,
    *,
    start_time: datetime,
    end_time: datetime,
) -> list[dict]:
    """Fetch calendar events using HighLevel's current millisecond time format."""
    if not SYNAMATE_API_TOKEN or not SYNAMATE_LOCATION_ID:
        return []

    def to_millis(value: datetime) -> int:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)

    headers = {
        "Authorization": f"Bearer {SYNAMATE_API_TOKEN}",
        "Version": "v3",
        "Accept": "application/json",
    }
    try:
        response = httpx.get(
            f"{SYNAMATE_BASE_URL}/calendars/events",
            headers=headers,
            params={
                "locationId": SYNAMATE_LOCATION_ID,
                "calendarId": calendar_id,
                "startTime": str(to_millis(start_time)),
                "endTime": str(to_millis(end_time)),
            },
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
        events = data.get("events") if isinstance(data, dict) else None
        return [event for event in (events or []) if isinstance(event, dict)]
    except Exception:
        logger.exception("Synamate calendar event lookup failed for %s", calendar_id)
        return []


def find_matching_clarity_event(
    *,
    calendar_id: str,
    phone: str,
    submitted_at: datetime | None = None,
) -> tuple[dict, dict] | None:
    """Find a non-cancelled clarity booking that belongs to this prospect."""
    now = datetime.now(timezone.utc)
    if submitted_at is None:
        start = now - timedelta(days=30)
    else:
        start = submitted_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start = start.astimezone(timezone.utc) - timedelta(days=1)
    end = now + timedelta(days=180)

    for event in get_synamate_calendar_events(
        calendar_id, start_time=start, end_time=end
    ):
        status = str(event.get("appointmentStatus") or event.get("status") or "").lower()
        if status in {"cancelled", "canceled", "invalid"}:
            continue
        contact_id = event.get("contactId") or event.get("contact_id")
        if not contact_id:
            continue
        contact = get_synamate_contact(str(contact_id)) or {}
        if _phones_match(contact.get("phone"), phone):
            return event, contact
    return None
