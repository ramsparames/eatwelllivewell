from datetime import datetime, timezone
from typing import Any


def can_manually_recover(
    interest: dict[str, Any] | None,
    payment: dict[str, Any] | None,
) -> bool:
    if not interest or not payment:
        return False
    return (
        (interest.get("status") or "pending") == "pending"
        and (payment.get("status") or "").lower() == "paid"
    )


def build_manual_recovery_appointment(
    interest: dict[str, Any],
    *,
    calendar_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not interest.get("id"):
        raise ValueError("Transformation interest ID is required")
    if not interest.get("phone"):
        raise ValueError("Transformation interest phone is required")
    if not calendar_id:
        raise ValueError("Clarity calendar ID is required")

    confirmed_at = now or datetime.now(timezone.utc)
    if confirmed_at.tzinfo is None:
        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)

    interest_id = int(interest["id"])
    start_time = confirmed_at.astimezone(timezone.utc).isoformat()

    return {
        "external_appointment_id": f"manual-recovery:interest:{interest_id}",
        "calendar_id": calendar_id,
        "contact_id": None,
        "name": interest.get("name") or "Transformation lead",
        "email": None,
        "phone": interest.get("phone"),
        "appointment_status": "confirmed",
        "title": "Clarity Call with Sushma (admin recovery)",
        "meeting_location": None,
        "start_time": start_time,
        "end_time": None,
        "raw_payload": {
            "source": "admin_manual_recovery",
            "interest_id": interest_id,
            "confirmed_at": start_time,
        },
    }
