from datetime import datetime, timedelta, timezone

import httpx

from app.config import (
    SYNAMATE_API_TOKEN,
    SYNAMATE_LOCATION_ID,
)

BASE_URL = "https://services.leadconnectorhq.com"


def get_calendar_events(
    calendar_id: str,
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict:
    if not SYNAMATE_API_TOKEN:
        raise RuntimeError("SYNAMATE_API_TOKEN is not configured")

    if not SYNAMATE_LOCATION_ID:
        raise RuntimeError("SYNAMATE_LOCATION_ID is not configured")

    now = datetime.now(timezone.utc)

    if start_time is None:
        start_time = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    if end_time is None:
        end_time = start_time + timedelta(days=1)

    headers = {
        "Authorization": f"Bearer {SYNAMATE_API_TOKEN}",
        "Version": "2021-07-28",
        "Accept": "application/json",
    }

    response = httpx.get(
        f"{BASE_URL}/calendars/events",
        headers=headers,
        params={
            "locationId": SYNAMATE_LOCATION_ID,
            "calendarId": calendar_id,
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()
