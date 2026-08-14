from datetime import date, datetime
from typing import Any

from app.database import get_connection


RESOURCE_TYPES = [
    "workout",
    "video",
    "guide",
    "audio",
    "recipe",
    "link",
]

RESOURCE_CATEGORIES = [
    "Strength",
    "Mobility",
    "Walking",
    "Nutrition",
    "Protein",
    "Sleep",
    "Stress",
    "Meditation",
    "Menopause",
    "Recipes",
    "Mindset",
    "Other",
]


def create_phase_a_tables() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS coach_resources (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    resource_type TEXT NOT NULL DEFAULT 'video',
                    category TEXT NOT NULL DEFAULT 'Other',
                    description TEXT,
                    resource_url TEXT NOT NULL,
                    duration_minutes INTEGER,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_resource_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id) ON DELETE CASCADE,
                    resource_id BIGINT NOT NULL
                        REFERENCES coach_resources(id) ON DELETE CASCADE,
                    assigned_on DATE NOT NULL DEFAULT CURRENT_DATE,
                    coach_note TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_client_resource_assignment_active
                ON client_resource_assignments(client_id, resource_id)
                WHERE status = 'active'
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_resource_assignments_client
                ON client_resource_assignments(client_id, assigned_on DESC)
                """
            )


def list_resources(active_only: bool = True):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if active_only:
                cursor.execute(
                    """
                    SELECT *
                    FROM coach_resources
                    WHERE active = TRUE
                    ORDER BY category, title
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM coach_resources
                    ORDER BY active DESC, category, title
                    """
                )
            return cursor.fetchall()


def create_resource(
    title: str,
    resource_type: str,
    category: str,
    description: str | None,
    resource_url: str,
    duration_minutes: int | None,
):
    resource_type = (
        resource_type if resource_type in RESOURCE_TYPES else "link"
    )
    category = (
        category if category in RESOURCE_CATEGORIES else "Other"
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO coach_resources (
                    title,
                    resource_type,
                    category,
                    description,
                    resource_url,
                    duration_minutes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    title,
                    resource_type,
                    category,
                    description,
                    resource_url,
                    duration_minutes,
                ),
            )
            row = cursor.fetchone()
            return int(row["id"])


def archive_resource(resource_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE coach_resources
                SET active = FALSE,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (resource_id,),
            )


def assign_resource(
    client_id: int,
    resource_id: int,
    coach_note: str | None = None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO client_resource_assignments (
                    client_id,
                    resource_id,
                    assigned_on,
                    coach_note,
                    status
                )
                VALUES (%s, %s, CURRENT_DATE, %s, 'active')
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (client_id, resource_id, coach_note),
            )
            row = cursor.fetchone()
            return int(row["id"]) if row else None


def unassign_resource(client_id: int, assignment_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE client_resource_assignments
                SET status = 'removed',
                    updated_at = NOW()
                WHERE id = %s
                  AND client_id = %s
                """,
                (assignment_id, client_id),
            )


def get_client_resources(client_id: int, active_only: bool = True):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                    a.id AS assignment_id,
                    a.client_id,
                    a.assigned_on,
                    a.coach_note,
                    a.status,
                    r.id AS resource_id,
                    r.title,
                    r.resource_type,
                    r.category,
                    r.description,
                    r.resource_url,
                    r.duration_minutes
                FROM client_resource_assignments a
                JOIN coach_resources r
                  ON r.id = a.resource_id
                WHERE a.client_id = %s
            """
            params: list[Any] = [client_id]

            if active_only:
                sql += " AND a.status = 'active' AND r.active = TRUE"

            sql += " ORDER BY a.assigned_on DESC, a.id DESC"
            cursor.execute(sql, params)
            return cursor.fetchall()


def build_client_timeline(client: dict, limit: int = 60):
    """
    One chronological coaching record built from data already captured in
    NourisHer. No duplicate timeline-entry form is required.
    """
    client_id = client["id"]
    items = []

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT intake_date, primary_goal, coach_focus
                FROM client_intakes
                WHERE client_id = %s
                LIMIT 1
                """,
                (client_id,),
            )
            intake = cursor.fetchone()
            if intake:
                detail_parts = []
                if intake.get("primary_goal"):
                    detail_parts.append(f"Goal: {intake['primary_goal']}")
                if intake.get("coach_focus"):
                    detail_parts.append(f"Coach focus: {intake['coach_focus']}")
                items.append(
                    {
                        "event_date": intake["intake_date"],
                        "event_type": "intake",
                        "label": "Client intake completed",
                        "detail": " · ".join(detail_parts),
                    }
                )

            cursor.execute(
                """
                SELECT
                    call_date,
                    week_number,
                    wins,
                    struggles,
                    improvements_needed,
                    coach_support
                FROM client_weekly_checkins
                WHERE client_id = %s
                ORDER BY call_date DESC, id DESC
                """,
                (client_id,),
            )
            for row in cursor.fetchall():
                detail_parts = []
                if row.get("wins"):
                    detail_parts.append(f"Wins: {row['wins']}")
                if row.get("improvements_needed"):
                    detail_parts.append(
                        f"Next focus: {row['improvements_needed']}"
                    )
                items.append(
                    {
                        "event_date": row["call_date"],
                        "event_type": "review",
                        "label": (
                            f"Week {row['week_number']} review"
                            if row.get("week_number")
                            else "Weekly coaching review"
                        ),
                        "detail": " · ".join(detail_parts),
                    }
                )

            cursor.execute(
                """
                SELECT
                    start_date,
                    action_name,
                    target_count,
                    target_unit
                FROM client_action_plans
                WHERE client_id = %s
                ORDER BY start_date DESC, id DESC
                """,
                (client_id,),
            )
            for row in cursor.fetchall():
                target = ""
                if row.get("target_count"):
                    target = (
                        f" · {row['target_count']} "
                        f"{row.get('target_unit') or ''}"
                    )
                items.append(
                    {
                        "event_date": row["start_date"],
                        "event_type": "action",
                        "label": f"Commitment assigned: {row['action_name']}",
                        "detail": target.strip(" ·"),
                    }
                )

            cursor.execute(
                """
                SELECT measured_on, weight_kg
                FROM client_measurements
                WHERE client_id = %s
                ORDER BY measured_on DESC, id DESC
                """,
                (client_id,),
            )
            for row in cursor.fetchall():
                detail = (
                    f"Weight {row['weight_kg']} kg"
                    if row.get("weight_kg") is not None
                    else "Weekly body measurements recorded"
                )
                items.append(
                    {
                        "event_date": row["measured_on"],
                        "event_type": "measurement",
                        "label": "Measurements recorded",
                        "detail": detail,
                    }
                )

            cursor.execute(
                """
                SELECT
                    a.assigned_on,
                    r.title,
                    r.resource_type,
                    r.category
                FROM client_resource_assignments a
                JOIN coach_resources r ON r.id = a.resource_id
                WHERE a.client_id = %s
                  AND a.status = 'active'
                ORDER BY a.assigned_on DESC, a.id DESC
                """,
                (client_id,),
            )
            for row in cursor.fetchall():
                items.append(
                    {
                        "event_date": row["assigned_on"],
                        "event_type": "resource",
                        "label": f"Resource assigned: {row['title']}",
                        "detail": (
                            f"{row['category']} · "
                            f"{row['resource_type'].title()}"
                        ),
                    }
                )

            # Include Synamate appointments when the contact can be matched.
            email = (client.get("email") or "").strip().lower()
            phone_digits = "".join(
                ch for ch in (client.get("phone") or "") if ch.isdigit()
            )

            if email or phone_digits:
                cursor.execute(
                    """
                    SELECT
                        start_time,
                        title,
                        appointment_status
                    FROM clarity_call_appointments
                    WHERE
                        (%s <> '' AND LOWER(COALESCE(email, '')) = %s)
                        OR
                        (
                            %s <> ''
                            AND REGEXP_REPLACE(
                                COALESCE(phone, ''),
                                '[^0-9]',
                                '',
                                'g'
                            ) = %s
                        )
                    ORDER BY start_time DESC
                    """,
                    (email, email, phone_digits, phone_digits),
                )
                for row in cursor.fetchall():
                    start_time = row["start_time"]
                    items.append(
                        {
                            "event_date": (
                                start_time.date()
                                if hasattr(start_time, "date")
                                else start_time
                            ),
                            "event_type": "call",
                            "label": row.get("title") or "Coaching call",
                            "detail": (
                                row.get("appointment_status") or "scheduled"
                            ).title(),
                        }
                    )

    def sort_key(item):
        value = item["event_date"]
        if isinstance(value, datetime):
            return value
        return datetime.combine(value, datetime.min.time())

    items.sort(key=sort_key, reverse=True)
    return items[:limit]


def build_coach_summary(call_prep: dict | None, progress_summary: dict | None):
    """
    Data-driven coach briefing. This intentionally works without an external
    AI API so every client gets a reliable summary immediately.
    """
    if not call_prep:
        return {
            "headline": "Not enough client data yet",
            "observations": [
                "Use this week to establish the client’s baseline and priorities."
            ],
            "focus": "Clarify the smallest useful next action.",
            "questions": [
                "What felt easiest this week?",
                "What got in the way most often?",
            ],
        }

    observations = []
    action_percent = int(call_prep.get("action_percent") or 0)
    submitted_count = int(call_prep.get("submitted_count") or 0)

    if submitted_count >= 6:
        observations.append(
            f"Daily tracking is strong: {submitted_count}/7 check-ins."
        )
    elif submitted_count >= 4:
        observations.append(
            f"Tracking is moderate: {submitted_count}/7 check-ins."
        )
    else:
        observations.append(
            f"Tracking needs support: only {submitted_count}/7 check-ins."
        )

    if action_percent >= 80:
        observations.append(
            f"Commitment adherence is strong at {action_percent}%."
        )
    elif action_percent >= 60:
        observations.append(
            f"Commitment adherence is building at {action_percent}%."
        )
    else:
        observations.append(
            f"Commitment adherence is low at {action_percent}%; simplify before adding more."
        )

    if call_prep.get("average_steps"):
        observations.append(
            f"Average steps: {call_prep['average_steps']}."
        )

    if call_prep.get("weight_change") is not None:
        change = float(call_prep["weight_change"])
        observations.append(
            f"Recorded weight change this week: {change:+.1f} kg."
        )

    if call_prep.get("attention"):
        focus = call_prep["attention"][0]
    elif action_percent < 60:
        focus = "Reduce friction and choose fewer, more achievable commitments."
    elif action_percent >= 80:
        focus = "Protect what is working and progress only one variable."
    else:
        focus = "Identify the one commitment that will create the biggest next-week win."

    headline = (
        "Strong week — consolidate the wins"
        if action_percent >= 80 and submitted_count >= 5
        else "Good data — refine the plan"
        if submitted_count >= 4
        else "Reconnect, simplify and rebuild consistency"
    )

    questions = [
        "Which commitment gave you the biggest benefit this week?",
        "Where did the plan feel unrealistic or difficult?",
        "What support would make next week easier?",
    ]

    return {
        "headline": headline,
        "observations": observations[:4],
        "focus": focus,
        "questions": questions,
    }

# Ensure Phase A tables exist before any portal/workspace query can use them.
# This is intentionally module-level so import order cannot cause
# UndefinedTable errors in the client portal.
create_phase_a_tables()

