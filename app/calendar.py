import httpx

from app.config import (
    SYNAMATE_API_TOKEN,
    SYNAMATE_LOCATION_ID,
)

BASE_URL = "https://services.leadconnectorhq.com"


def get_calendar_events(calendar_id: str):
    headers = {
        "Authorization": f"Bearer {SYNAMATE_API_TOKEN}",
        "Version": "2021-07-28",
    }

    response = httpx.get(
        f"{BASE_URL}/calendars/events",
        headers=headers,
        params={
            "locationId": SYNAMATE_LOCATION_ID,
            "calendarId": calendar_id,
        },
        timeout=20,
    )

    print(response.status_code)
    print(response.text)

    response.raise_for_status()

    return response.json()
