import logging

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
