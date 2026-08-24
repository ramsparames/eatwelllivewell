from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from app.database import get_connection


NUDGE_COOLDOWN_HOURS = 48


def ensure_client_nudges_table() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_nudges (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id)
                        ON DELETE CASCADE,
                    reason TEXT NOT NULL,
                    message TEXT NOT NULL,
                    channel TEXT NOT NULL DEFAULT 'whatsapp_manual',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_client_nudges_client_created
                ON client_nudges(client_id, created_at DESC)
                """
            )


def _first_name(name: str | None) -> str:
    clean = (name or "there").strip()
    return clean.split()[0] if clean else "there"


def default_nudge_message(
    *,
    client_name: str | None,
    reason: str,
) -> str:
    first_name = _first_name(client_name)

    messages = {
        "missed_tracking": (
            f"Hi {first_name} 😊 Just a gentle reminder to update your "
            "NourisHer tracker when you get a chance today. It helps me "
            "understand how your week is going and support you better. 💜 "
            "— Sushma"
        ),
        "low_adherence": (
            f"Hi {first_name} 😊 Just checking in. I noticed this week has "
            "been a little harder to stay consistent with the actions we "
            "planned. No pressure — when you get a moment, update your "
            "tracker and we can work with what is realistic for you this "
            "week. 💜 — Sushma"
        ),
        "workout": (
            f"Hi {first_name} 😊 A gentle reminder about your strength "
            "workout when you get a chance. Even getting one session done "
            "is a useful win — record it in NourisHer once completed. 💜 "
            "— Sushma"
        ),
        "reflection": (
            f"Hi {first_name} 😊 When you get a moment, please complete "
            "your weekly NourisHer reflection. It helps me review your week "
            "and plan the right focus with you. 💜 — Sushma"
        ),
        "custom": (
            f"Hi {first_name} 😊 Just checking in with you. 💜 — Sushma"
        ),
    }
    return messages.get(reason) or messages["custom"]


def get_latest_client_nudges(
    client_ids: list[int],
) -> dict[int, dict]:
    if not client_ids:
        return {}

    ensure_client_nudges_table()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (client_id)
                    id,
                    client_id,
                    reason,
                    message,
                    channel,
                    created_at
                FROM client_nudges
                WHERE client_id = ANY(%s)
                ORDER BY client_id, created_at DESC
                """,
                (client_ids,),
            )
            rows = cursor.fetchall()

    return {
        row["client_id"]: dict(row)
        for row in rows
    }


def nudge_is_recent(
    last_nudge: dict | None,
    *,
    now: datetime | None = None,
) -> bool:
    if not last_nudge or not last_nudge.get("created_at"):
        return False

    current = now or datetime.now(timezone.utc)
    created_at = last_nudge["created_at"]
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return current - created_at < timedelta(
        hours=NUDGE_COOLDOWN_HOURS
    )


def record_client_nudge(
    *,
    client_id: int,
    reason: str,
    message: str,
) -> dict:
    ensure_client_nudges_table()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO client_nudges (
                    client_id,
                    reason,
                    message,
                    channel
                )
                VALUES (%s, %s, %s, 'whatsapp_manual')
                RETURNING
                    id,
                    client_id,
                    reason,
                    message,
                    channel,
                    created_at
                """,
                (
                    client_id,
                    reason,
                    message,
                ),
            )
            row = cursor.fetchone()

    return dict(row)


def whatsapp_prefilled_url(
    *,
    phone: str | None,
    message: str,
) -> str:
    digits = "".join(
        character
        for character in (phone or "")
        if character.isdigit()
    )

    if not digits:
        raise ValueError(
            "This client does not have a WhatsApp phone number."
        )

    return (
        f"https://wa.me/{digits}"
        f"?text={quote(message)}"
    )
