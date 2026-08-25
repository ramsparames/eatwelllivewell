import secrets
from datetime import date, timedelta

from app.database import get_connection
from app.services.client_service import ClientService



def _latest_client_coach_feedback(client_id: int):
    """Latest client-visible coaching note. Private coach notes are never returned."""
    for checkin in (ClientService.checkins(client_id) or []):
        note = (checkin.get("client_feedback") or "").strip()
        if note:
            return {"note": note, "call_date": checkin.get("call_date")}
    return None

def create_portal_tables() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_portal_access (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL UNIQUE
                        REFERENCES clients(id) ON DELETE CASCADE,
                    access_token TEXT NOT NULL UNIQUE,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Daily action logs reference the same action-plan rows used
            # by the coach workspace.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_action_daily_logs (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id) ON DELETE CASCADE,
                    action_id INTEGER NOT NULL,
                    tracked_on DATE NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (action_id, tracked_on)
                )
            """)

            # Mark a portal day as formally submitted. This is kept separate
            # from client_daily_tracking because the coach can also add rows
            # to that table manually.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_portal_daily_submissions (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id) ON DELETE CASCADE,
                    tracked_on DATE NOT NULL,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (client_id, tracked_on)
                )
            """)

            # Align older builds with client_action_plans.
            cursor.execute("""
                ALTER TABLE client_action_daily_logs
                DROP CONSTRAINT IF EXISTS
                    client_action_daily_logs_action_id_fkey
            """)

            cursor.execute("""
                DELETE FROM client_action_daily_logs l
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM client_action_plans p
                    WHERE p.id = l.action_id
                )
            """)

            cursor.execute("""
                ALTER TABLE client_action_daily_logs
                ADD CONSTRAINT client_action_daily_logs_action_id_fkey
                FOREIGN KEY (action_id)
                REFERENCES client_action_plans(id)
                ON DELETE CASCADE
            """)


def get_portal_access(client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, client_id, access_token, enabled,
                       created_at, updated_at
                FROM client_portal_access
                WHERE client_id = %s
                LIMIT 1
            """, (client_id,))
            return cursor.fetchone()


def ensure_portal_access(client_id: int):
    existing = get_portal_access(client_id)
    if existing:
        return existing

    token = secrets.token_urlsafe(32)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO client_portal_access (
                    client_id, access_token
                )
                VALUES (%s, %s)
                RETURNING id, client_id, access_token, enabled,
                          created_at, updated_at
            """, (client_id, token))
            return cursor.fetchone()


def get_client_by_token(access_token: str):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.id, c.name, c.email, c.phone,
                       c.program, c.status, c.start_date,
                       p.access_token, p.enabled
                FROM client_portal_access p
                JOIN clients c ON c.id = p.client_id
                WHERE p.access_token = %s
                  AND p.enabled = TRUE
                LIMIT 1
            """, (access_token,))
            return cursor.fetchone()


def get_active_actions(client_id: int):
    # Uses the same source as the coach workspace.
    actions = ClientService.actions(
        client_id,
        status="active",
    )
    return [dict(action) for action in actions]


def is_portal_day_submitted(client_id: int, tracked_on: date) -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM client_portal_daily_submissions
                WHERE client_id = %s
                  AND tracked_on = %s
                LIMIT 1
            """, (client_id, tracked_on))
            return cursor.fetchone() is not None


def get_action_logs_for_date(client_id: int, tracked_on: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT action_id, completed
                FROM client_action_daily_logs
                WHERE client_id = %s
                  AND tracked_on = %s
            """, (client_id, tracked_on))
            rows = cursor.fetchall()

    return {
        row["action_id"]: row["completed"]
        for row in rows
    }


def save_action_logs(
    client_id: int,
    tracked_on: date,
    active_action_ids: list[int],
    completed_action_ids: list[int],
):
    # Submitted portal days are immutable.
    if is_portal_day_submitted(client_id, tracked_on):
        return

    completed_set = set(completed_action_ids)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for action_id in active_action_ids:
                cursor.execute("""
                    INSERT INTO client_action_daily_logs (
                        client_id, action_id, tracked_on, completed
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (action_id, tracked_on)
                    DO UPDATE SET
                        completed = EXCLUDED.completed,
                        updated_at = NOW()
                """, (
                    client_id,
                    action_id,
                    tracked_on,
                    action_id in completed_set,
                ))


def get_daily_tracking_for_date(client_id: int, tracked_on: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.client_id,
                    t.tracked_on,
                    t.steps,
                    t.weight_kg,
                    t.note,
                    s.submitted_at,
                    (s.id IS NOT NULL) AS is_submitted
                FROM client_daily_tracking t
                LEFT JOIN client_portal_daily_submissions s
                  ON s.client_id = t.client_id
                 AND s.tracked_on = t.tracked_on
                WHERE t.client_id = %s
                  AND t.tracked_on = %s
                LIMIT 1
            """, (client_id, tracked_on))
            row = cursor.fetchone()

            if row:
                return row

            # Still return submission state if a very old/partial request
            # somehow created the submission marker without tracking values.
            cursor.execute("""
                SELECT
                    %s::INTEGER AS client_id,
                    %s::DATE AS tracked_on,
                    NULL::INTEGER AS steps,
                    NULL::NUMERIC AS weight_kg,
                    NULL::TEXT AS note,
                    submitted_at,
                    TRUE AS is_submitted
                FROM client_portal_daily_submissions
                WHERE client_id = %s
                  AND tracked_on = %s
                LIMIT 1
            """, (client_id, tracked_on, client_id, tracked_on))
            return cursor.fetchone()


def save_client_daily_entry(
    client_id: int,
    tracked_on: date,
    steps: int | None,
    weight_kg: float | None,
    note: str | None,
):
    # One submission per day. Once submitted, it remains read-only.
    if is_portal_day_submitted(client_id, tracked_on):
        return

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO client_daily_tracking (
                    client_id, tracked_on, steps, weight_kg, note
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id, tracked_on)
                DO UPDATE SET
                    steps = EXCLUDED.steps,
                    weight_kg = EXCLUDED.weight_kg,
                    note = EXCLUDED.note,
                    updated_at = NOW()
            """, (
                client_id,
                tracked_on,
                steps,
                weight_kg,
                note,
            ))

            cursor.execute("""
                INSERT INTO client_portal_daily_submissions (
                    client_id, tracked_on
                )
                VALUES (%s, %s)
                ON CONFLICT (client_id, tracked_on)
                DO NOTHING
            """, (client_id, tracked_on))


def get_recent_client_activity(client_id: int, limit: int = 14):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.tracked_on,
                    t.steps,
                    t.weight_kg,
                    t.note,
                    COUNT(l.id) AS actions_total,
                    COUNT(l.id) FILTER (
                        WHERE l.completed = TRUE
                    ) AS actions_completed
                FROM client_daily_tracking t
                LEFT JOIN client_action_daily_logs l
                  ON l.client_id = t.client_id
                 AND l.tracked_on = t.tracked_on
                WHERE t.client_id = %s
                GROUP BY
                    t.tracked_on,
                    t.steps,
                    t.weight_kg,
                    t.note
                ORDER BY t.tracked_on DESC
                LIMIT %s
            """, (client_id, limit))
            return cursor.fetchall()


def _coaching_week(client_id: int, today: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT start_date
                FROM clients
                WHERE id = %s
                LIMIT 1
            """, (client_id,))
            client = cursor.fetchone()

    start_date = client["start_date"] if client else None

    if start_date and today >= start_date:
        elapsed = (today - start_date).days
        week_number = (elapsed // 7) + 1
        week_start = start_date + timedelta(days=(week_number - 1) * 7)
    elif start_date:
        week_number = 1
        week_start = start_date
    else:
        # Safe fallback when a client has no coaching start date yet.
        week_number = 1
        week_start = today

    return week_number, week_start, week_start + timedelta(days=6)


def get_week_completion(client_id: int):
    """
    Client-specific coaching week, not Monday-Sunday.

    Returns:
    - Week number + actual date range
    - 7 date rows
    - submitted-day count
    - read-only detail for submitted dates
    """
    today = date.today()
    week_number, week_start, week_end = _coaching_week(client_id, today)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.tracked_on,
                    t.steps,
                    t.weight_kg,
                    t.note,
                    s.submitted_at
                FROM client_portal_daily_submissions s
                LEFT JOIN client_daily_tracking t
                  ON t.client_id = s.client_id
                 AND t.tracked_on = s.tracked_on
                WHERE s.client_id = %s
                  AND s.tracked_on BETWEEN %s AND %s
                ORDER BY s.tracked_on
            """, (client_id, week_start, week_end))
            tracking_rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    l.tracked_on,
                    l.action_id,
                    l.completed,
                    p.action_name,
                    p.target_count,
                    p.target_unit
                FROM client_action_daily_logs l
                JOIN client_action_plans p
                  ON p.id = l.action_id
                WHERE l.client_id = %s
                  AND l.tracked_on BETWEEN %s AND %s
                ORDER BY l.tracked_on, p.id
            """, (client_id, week_start, week_end))
            action_rows = cursor.fetchall()

    tracking_by_date = {
        row["tracked_on"]: dict(row)
        for row in tracking_rows
    }

    actions_by_date = {}
    for row in action_rows:
        actions_by_date.setdefault(row["tracked_on"], []).append(dict(row))

    days = []
    submitted_days = 0

    for offset in range(7):
        day_date = week_start + timedelta(days=offset)
        tracking = tracking_by_date.get(day_date)
        submitted = tracking is not None

        if submitted:
            submitted_days += 1

        if submitted:
            state = "submitted"
        elif day_date == today:
            state = "today"
        elif day_date < today:
            state = "missed"
        else:
            state = "upcoming"

        day_actions = actions_by_date.get(day_date, [])
        completed_actions = sum(
            1 for item in day_actions if item.get("completed")
        )

        days.append({
            "date": day_date,
            "state": state,
            "submitted": submitted,
            "steps": tracking.get("steps") if tracking else None,
            "weight_kg": tracking.get("weight_kg") if tracking else None,
            "note": tracking.get("note") if tracking else None,
            "submitted_at": tracking.get("submitted_at") if tracking else None,
            "actions": day_actions,
            "actions_total": len(day_actions),
            "actions_completed": completed_actions,
        })

    checkin_percent = round((submitted_days / 7) * 100)

    # Keep old keys for any other existing caller/template.
    return {
        "week_number": week_number,
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "checkins_completed": submitted_days,
        "checkins_total": 7,
        "checkin_percent": checkin_percent,
        "total": 7,
        "completed": submitted_days,
        "percent": checkin_percent,
    }
