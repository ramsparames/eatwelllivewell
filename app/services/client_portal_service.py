import os
import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.database import get_next_synamate_appointment_for_person, get_previous_measurement_before, resolve_synamate_calendar_id
from app.database import get_connection
from app.services.client_service import ClientService


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


def get_actions_for_date(client_id: int, tracked_on: date):
    """
    Return only assignments that belong to the selected coaching date.
    A row may remain status='active' after its week ends, so date boundaries
    are part of the source of truth for the client portal.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM client_action_plans
                WHERE client_id = %s
                  AND status = 'active'
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date >= %s)
                ORDER BY id
                """,
                (client_id, tracked_on, tracked_on),
            )
            return [dict(row) for row in cursor.fetchall()]


def get_editable_week_dates(client_id: int, on_date: date):
    _, week_start, week_end = _coaching_week(client_id, on_date)
    last_editable = min(on_date, week_end)
    dates = []
    cursor_date = week_start
    while cursor_date <= last_editable:
        dates.append(cursor_date)
        cursor_date += timedelta(days=1)
    return dates


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
    # Current coaching-week days remain editable. Re-submission simply
    # overwrites that date's action state.
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
    note: str | None = None,
):
    """
    Daily client submission:
    actions are saved separately; this row stores steps and optional weight.
    Current coaching-week days may be submitted more than once.
    """
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
                None,
            ))

            cursor.execute("""
                INSERT INTO client_portal_daily_submissions (
                    client_id, tracked_on
                )
                VALUES (%s, %s)
                ON CONFLICT (client_id, tracked_on)
                DO UPDATE SET
                    submitted_at = NOW()
            """, (client_id, tracked_on))


def get_current_week_measurement(client_id: int, on_date: date | None = None):
    """
    Return the latest body-measurement entry in the client's current coaching week.
    The portal allows only one weekly measurement submission.
    """
    today = on_date or date.today()
    _, week_start, week_end = _coaching_week(client_id, today)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM client_measurements
                WHERE client_id = %s
                  AND measured_on BETWEEN %s AND %s
                  AND (
                      upper_arm_cm IS NOT NULL OR
                      chest_cm IS NOT NULL OR
                      waist_cm IS NOT NULL OR
                      lower_abdomen_cm IS NOT NULL OR
                      hip_cm IS NOT NULL OR
                      thigh_cm IS NOT NULL
                  )
                ORDER BY measured_on DESC, id DESC
                LIMIT 1
            """, (client_id, week_start, week_end))
            return cursor.fetchone()


def save_weekly_measurements(
    client_id: int,
    measured_on: date,
    on_date: date | None = None,
    upper_arm: float | None = None,
    chest: float | None = None,
    waist: float | None = None,
    lower_abdomen: float | None = None,
    hip: float | None = None,
    thigh: float | None = None,
    measurement_unit: str = "cm",
):
    """
    Save body measurements once per coaching week.
    The client chooses the actual date on which she measured.
    """
    today = on_date or date.today()
    _, week_start, week_end = _coaching_week(client_id, today)

    if measured_on < week_start or measured_on > week_end:
        raise ValueError("Measurement date must fall within the current coaching week.")

    if measured_on > today:
        raise ValueError("Measurement date cannot be in the future.")

    if get_current_week_measurement(client_id, on_date=today):
        return False

    values = [
        upper_arm,
        chest,
        waist,
        lower_abdomen,
        hip,
        thigh,
    ]
    if any(value is None for value in values):
        raise ValueError(
            "All weekly body measurements are required."
        )

    ClientService.add_measurement(
        client_id=client_id,
        measured_on=measured_on,
        weight_kg=None,
        upper_arm=upper_arm,
        chest=chest,
        waist=waist,
        lower_abdomen=lower_abdomen,
        hip=hip,
        thigh=thigh,
        measurement_unit=(
            measurement_unit
            if measurement_unit in {"cm", "inches"}
            else "cm"
        ),
        checkin_id=None,
    )
    return True



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


def get_week_completion(client_id: int, on_date: date | None = None):
    """
    Client-specific coaching week, not Monday-Sunday.

    Returns:
    - Week number + actual date range
    - 7 date rows
    - submitted-day count
    - read-only detail for submitted dates
    """
    today = on_date or date.today()
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
                SELECT DISTINCT ON (measured_on)
                    measured_on, weight_kg, upper_arm_cm, chest_cm, waist_cm,
                    lower_abdomen_cm, hip_cm, thigh_cm
                FROM client_measurements
                WHERE client_id = %s
                  AND measured_on BETWEEN %s AND %s
                ORDER BY measured_on, id DESC
            """, (client_id, week_start, week_end))
            measurement_rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    l.tracked_on,
                    l.action_id,
                    l.completed,
                    p.action_name,
                    p.action_key,
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

    measurements_by_date = {
        row["measured_on"]: dict(row)
        for row in measurement_rows
    }

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
            state = "open"
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
            "measurements": measurements_by_date.get(day_date),
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



def get_coaching_week_view(
    client_id: int,
    week_number: int,
    on_date: date | None = None,
):
    """
    Return one specific coaching week for the client.

    Past weeks are read-only.
    Current week is editable through today.
    Future weeks can be viewed, but not edited.
    """
    today = on_date or date.today()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT start_date
                FROM clients
                WHERE id = %s
                LIMIT 1
                """,
                (client_id,),
            )
            client = cursor.fetchone()

    if not client or not client.get("start_date"):
        return None

    current_week_number, _, _ = _coaching_week(client_id, today)
    week_number = max(1, int(week_number))

    week_start = client["start_date"] + timedelta(
        days=(week_number - 1) * 7
    )
    week_end = week_start + timedelta(days=6)

    review = get_coach_week_review(
        client_id,
        week_start,
        week_end,
    )

    days = []
    for day in review["days"]:
        row = dict(day)

        if week_number < current_week_number:
            state = "read_only"
            editable = False
        elif week_number > current_week_number:
            state = "upcoming"
            editable = False
        else:
            if day["date"] > today:
                state = "upcoming"
                editable = False
            elif day["date"] == today:
                state = "today"
                editable = True
            else:
                state = "open"
                editable = True

        row["browser_state"] = state
        row["editable"] = editable
        days.append(row)

    measurement = (
        review["measurements"][0]
        if review["measurements"]
        else None
    )

    return {
        "week_number": week_number,
        "current_week_number": current_week_number,
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "submitted_count": review["submitted_count"],
        "measurement": measurement,
        "is_current": week_number == current_week_number,
        "is_past": week_number < current_week_number,
        "is_future": week_number > current_week_number,
        "can_go_previous": week_number > 1,
        "can_go_next": week_number < current_week_number + 1,
    }



def get_coach_history_grid(
    client_id: int,
    on_date: date | None = None,
):
    """All coaching weeks in one grid, keyed by stable action identity."""
    today = on_date or date.today()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT start_date FROM clients WHERE id = %s LIMIT 1",
                (client_id,),
            )
            client = cursor.fetchone()

    if not client or not client.get("start_date"):
        return {
            "action_columns": [],
            "rows": [],
            "current_week_number": 0,
        }

    def fallback_key(action):
        name = " ".join((action.get("action_name") or "").strip().lower().split())
        return f"legacy:{name}"

    current_week_number, _, _ = _coaching_week(client_id, today)
    all_actions = {}
    rows = []

    for week_number in range(1, current_week_number + 1):
        week_start = client["start_date"] + timedelta(days=(week_number - 1) * 7)
        week_end = week_start + timedelta(days=6)
        review = get_coach_week_review(client_id, week_start, week_end)

        for action in review["actions"]:
            key = (action.get("action_key") or "").strip() or fallback_key(action)
            if key not in all_actions:
                all_actions[key] = {
                    "id": key,
                    "action_key": key,
                    "name": action["action_name"],
                    "target_count": action.get("target_count"),
                    "target_unit": action.get("target_unit"),
                }

        status_by_key = {}
        for action in review["actions"]:
            key = (action.get("action_key") or "").strip() or fallback_key(action)
            for result in action["days"]:
                status_by_key[(result["date"], key)] = {
                    "eligible": result["eligible"],
                    "completed": result["completed"],
                    "action_id": action["id"],
                    "action_key": key,
                    "action_name": action["action_name"],
                }

        measurement = review["measurements"][0] if review["measurements"] else None

        for day in review["days"]:
            rows.append({
                "week_number": week_number,
                "date": day["date"],
                "submitted": day["submitted"],
                "steps": day["steps"],
                "weight_kg": day["weight_kg"],
                "note": day["note"],
                "actions": dict(status_by_key),
                "measurement": (
                    measurement
                    if measurement and measurement.get("measured_on") == day["date"]
                    else None
                ),
                "is_current_week": week_number == current_week_number,
            })

    action_columns = list(all_actions.values())

    for row in rows:
        normalized = {}
        for action in action_columns:
            normalized[action["id"]] = row["actions"].get((row["date"], action["id"]))
        row["actions"] = normalized

    rows.sort(key=lambda row: (-row["week_number"], row["date"]))

    return {
        "action_columns": action_columns,
        "rows": rows,
        "current_week_number": current_week_number,
    }


def get_client_history_grid(
    client_id: int,
    on_date: date | None = None,
):
    """
    Client-facing spreadsheet history.

    Past weeks are read-only.
    Current week rows through today are editable.
    Future dates are visible but locked.
    """
    today = on_date or date.today()
    grid = get_coach_history_grid(client_id, on_date=today)
    current_week_number = grid.get("current_week_number") or 0

    for row in grid.get("rows", []):
        row["is_past_week"] = row["week_number"] < current_week_number
        row["is_future_day"] = (
            row["week_number"] == current_week_number
            and row["date"] > today
        )
        row["editable"] = (
            row["week_number"] == current_week_number
            and row["date"] <= today
        )

    # Build one weekly measurement summary per coaching week.
    week_measurements = {}
    for row in grid.get("rows", []):
        if row.get("measurement"):
            week_measurements[row["week_number"]] = row["measurement"]

    grid["week_measurements"] = week_measurements
    grid["today"] = today
    return grid


def get_client_operations_status(client: dict, on_date: date | None = None):
    """
    Production operations status for one active coaching client.
    Centralizes the rules used by the Coach Dashboard and Clients page.
    """
    client_id = client["id"]
    timezone_name = client.get("timezone") or "Asia/Kolkata"
    if on_date is None:
        on_date = datetime.now(ZoneInfo(timezone_name)).date()

    start_date = client.get("start_date")
    if not start_date:
        return {
            "health_key": "setup",
            "health_label": "Setup",
            "week_number": 0,
            "week_start": None,
            "week_end": None,
            "missed_daily_count": 0,
            "submitted_daily_count": 0,
            "measurement_due": False,
            "weekly_review_overdue": False,
            "no_next_call": True,
            "next_call": get_next_client_call(client),
            "reasons": ["Complete client setup"],
            "attention_count": 1,
        }

    week_number, week_start, week_end = _coaching_week(client_id, on_date)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tracked_on
                FROM client_portal_daily_submissions
                WHERE client_id = %s
                  AND tracked_on BETWEEN %s AND %s
                """,
                (client_id, week_start, week_end),
            )
            submitted_dates = {row["tracked_on"] for row in cursor.fetchall()}

            # This is the TRUE number of client-submitted days this coaching week.
            # Do not derive it from missed days: missed_daily_count intentionally
            # ignores today/future dates, which previously made a client with no
            # submissions appear as 7/7 early in the week.
            submitted_daily_count = sum(
                1
                for submitted_date in submitted_dates
                if week_start <= submitted_date <= min(on_date, week_end)
            )

            cursor.execute(
                """
                SELECT 1
                FROM client_measurements
                WHERE client_id = %s
                  AND measured_on BETWEEN %s AND %s
                LIMIT 1
                """,
                (client_id, week_start, week_end),
            )
            has_measurement = cursor.fetchone() is not None

            previous_review_done = True
            if week_number > 1:
                previous_week_end = week_start - timedelta(days=1)
                previous_week_start = previous_week_end - timedelta(days=6)
                cursor.execute(
                    """
                    SELECT 1
                    FROM client_weekly_checkins
                    WHERE client_id = %s
                      AND call_date BETWEEN %s AND %s
                    LIMIT 1
                    """,
                    (client_id, previous_week_start, previous_week_end),
                )
                previous_review_done = cursor.fetchone() is not None

    missed_dates = []
    cursor_date = week_start
    while cursor_date < on_date and cursor_date <= week_end:
        if cursor_date not in submitted_dates:
            missed_dates.append(cursor_date)
        cursor_date += timedelta(days=1)

    day_number = max(1, min(7, (on_date - week_start).days + 1))
    measurement_due = (not has_measurement) and day_number >= 5
    weekly_review_overdue = week_number > 1 and not previous_review_done
    next_call = get_next_client_call(client)
    no_next_call = next_call is None

    reasons = []
    if weekly_review_overdue:
        reasons.append("Weekly review overdue")
    if len(missed_dates) >= 2:
        reasons.append(f"{len(missed_dates)} missed daily updates")
    if measurement_due:
        reasons.append("Weekly measurements due")
    if no_next_call:
        reasons.append("Next coaching call not scheduled")

    if weekly_review_overdue or len(missed_dates) >= 2 or measurement_due or no_next_call:
        health_key = "attention"
        health_label = "Needs attention"
    elif len(missed_dates) == 1:
        health_key = "watch"
        health_label = "Watch"
    else:
        health_key = "on_track"
        health_label = "On track"

    return {
        "health_key": health_key,
        "health_label": health_label,
        "week_number": week_number,
        "week_start": week_start,
        "week_end": week_end,
        "missed_daily_count": len(missed_dates),
        "submitted_daily_count": submitted_daily_count,
        "measurement_due": measurement_due,
        "weekly_review_overdue": weekly_review_overdue,
        "no_next_call": no_next_call,
        "next_call": next_call,
        "reasons": reasons,
        "attention_count": len(reasons),
    }



def get_coach_week_review(
    client_id: int,
    week_start: date,
    week_end: date,
):
    """Coach-facing complete view of one client coaching week."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    s.tracked_on,
                    s.submitted_at,
                    t.steps,
                    t.weight_kg,
                    t.note
                FROM client_portal_daily_submissions s
                LEFT JOIN client_daily_tracking t
                  ON t.client_id = s.client_id
                 AND t.tracked_on = s.tracked_on
                WHERE s.client_id = %s
                  AND s.tracked_on BETWEEN %s AND %s
                ORDER BY s.tracked_on
            """, (client_id, week_start, week_end))
            submission_rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    p.id,
                    p.action_name,
                    p.target_count,
                    p.target_unit,
                    p.start_date,
                    p.end_date
                FROM client_action_plans p
                WHERE p.client_id = %s
                  AND p.start_date <= %s
                  AND (p.end_date IS NULL OR p.end_date >= %s)
                ORDER BY p.id
            """, (client_id, week_end, week_start))
            action_plan_rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    l.action_id,
                    l.tracked_on,
                    l.completed
                FROM client_action_daily_logs l
                WHERE l.client_id = %s
                  AND l.tracked_on BETWEEN %s AND %s
            """, (client_id, week_start, week_end))
            log_rows = cursor.fetchall()

            cursor.execute("""
                SELECT *
                FROM client_measurements
                WHERE client_id = %s
                  AND measured_on BETWEEN %s AND %s
                ORDER BY measured_on DESC, id DESC
            """, (client_id, week_start, week_end))
            measurement_rows = cursor.fetchall()

    submissions = {row["tracked_on"]: dict(row) for row in submission_rows}
    logs = {
        (row["action_id"], row["tracked_on"]): bool(row["completed"])
        for row in log_rows
    }

    days = []
    for offset in range(7):
        day_date = week_start + timedelta(days=offset)
        submitted = submissions.get(day_date)
        days.append({
            "date": day_date,
            "submitted": submitted is not None,
            "steps": submitted.get("steps") if submitted else None,
            "weight_kg": submitted.get("weight_kg") if submitted else None,
            "note": submitted.get("note") if submitted else None,
        })

    actions = []
    for plan in action_plan_rows:
        item = dict(plan)
        results = []
        completed_count = 0
        eligible_days = 0

        # Action plans are coaching-week commitments.
        #
        # Older records may have start/end dates that are slightly out of sync
        # with the client's actual coaching-week boundaries. If the action
        # overlaps this coaching week at all, treat it as eligible for the
        # full 7-day coaching week.
        action_overlaps_week = (
            item["start_date"] <= week_end
            and (
                item["end_date"] is None
                or item["end_date"] >= week_start
            )
        )

        for day in days:
            d = day["date"]
            eligible = action_overlaps_week
            completed = None

            if eligible:
                eligible_days += 1
                completed = logs.get((item["id"], d))
                if completed:
                    completed_count += 1

            results.append({
                "date": d,
                "eligible": eligible,
                "completed": completed,
            })

        item["days"] = results
        item["completed_count"] = completed_count
        item["eligible_days"] = eligible_days
        actions.append(item)

    return {
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
        "actions": actions,
        "measurements": [dict(row) for row in measurement_rows],
        "submitted_count": sum(1 for day in days if day["submitted"]),
    }



def _extract_synamate_link(payload, keywords):
    """Best-effort extraction of reschedule/cancel/booking URLs from webhook data."""
    if not isinstance(payload, dict):
        return None

    lowered_keywords = tuple(keyword.lower() for keyword in keywords)

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                key_lower = str(key).lower()
                if (
                    isinstance(child, str)
                    and child.startswith(('http://', 'https://'))
                    and any(keyword in key_lower for keyword in lowered_keywords)
                ):
                    return child
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return None

    return walk(payload)


def get_next_client_call(client: dict):
    coaching_calendar_id = resolve_synamate_calendar_id(
        role="coaching",
        expected_name=os.getenv(
            "SYNAMATE_COACHING_CALENDAR_NAME",
            "Coaching Call with Sushma",
        ).strip(),
        explicit_calendar_id=os.getenv(
            "SYNAMATE_COACHING_CALENDAR_ID",
            "",
        ).strip(),
    )

    if not coaching_calendar_id:
        return None

    appointment = get_next_synamate_appointment_for_person(
        email=client.get("email"),
        phone=client.get("phone"),
        calendar_id=coaching_calendar_id,
    )

    if not appointment:
        return None

    item = dict(appointment)
    payload = item.get("raw_payload") or {}
    item["source"] = "synamate"
    item["call_kind"] = "coaching"

    client_tz = ZoneInfo(client.get("timezone") or "Asia/Kolkata")
    item["local_start_time"] = (
        item["start_time"].astimezone(client_tz)
        if item.get("start_time")
        else None
    )
    item["reschedule_url"] = _extract_synamate_link(
        payload,
        ("reschedule", "rescheduleurl", "reschedule_url"),
    )
    item["cancel_url"] = _extract_synamate_link(
        payload,
        ("cancel", "cancelurl", "cancel_url"),
    )
    return item




def get_client_progress_summary(
    client_id: int,
    current_week_start: date,
    current_week_number: int,
    weeks: int = 4,
):
    """
    Compact week-by-week progress for the coach workspace.
    Uses the client's own coaching-week boundaries, never Mon-Sun.
    """
    rows = []

    first_week_number = max(1, current_week_number - weeks + 1)

    for week_number in range(first_week_number, current_week_number + 1):
        offset_weeks = current_week_number - week_number
        week_start = current_week_start - timedelta(days=7 * offset_weeks)
        week_end = week_start + timedelta(days=6)
        review = get_coach_week_review(client_id, week_start, week_end)

        target_total = 0
        achieved_total = 0

        for action in review["actions"]:
            target = int(
                action.get("target_count")
                or action.get("eligible_days")
                or 0
            )
            completed = int(action.get("completed_count") or 0)
            target_total += target
            achieved_total += min(completed, target) if target else completed

        action_percent = (
            round((achieved_total / target_total) * 100)
            if target_total
            else 0
        )

        step_values = [
            int(day["steps"])
            for day in review["days"]
            if day.get("submitted") and day.get("steps") is not None
        ]

        measurement = (
            review["measurements"][0]
            if review["measurements"]
            else None
        )

        rows.append(
            {
                "week_number": week_number,
                "week_start": week_start,
                "week_end": week_end,
                "submitted_count": review["submitted_count"],
                "checkin_percent": round(
                    (review["submitted_count"] / 7) * 100
                ),
                "action_percent": action_percent,
                "average_steps": (
                    round(sum(step_values) / len(step_values))
                    if step_values
                    else None
                ),
                "measurement_date": (
                    measurement.get("measured_on")
                    if measurement
                    else None
                ),
                "weight_kg": (
                    float(measurement["weight_kg"])
                    if measurement
                    and measurement.get("weight_kg") is not None
                    else None
                ),
            }
        )

    weights = [
        row["weight_kg"]
        for row in rows
        if row["weight_kg"] is not None
    ]

    return {
        "weeks": rows,
        "weight_change": (
            round(weights[-1] - weights[0], 1)
            if len(weights) >= 2
            else None
        ),
        "latest_action_percent": (
            rows[-1]["action_percent"]
            if rows
            else 0
        ),
        "latest_checkin_percent": (
            rows[-1]["checkin_percent"]
            if rows
            else 0
        ),
    }


def build_call_prep(client_id: int, week_start: date, week_end: date):
    """Create a compact pre-call summary from the client's current week."""
    review = get_coach_week_review(client_id, week_start, week_end)

    submitted_days = [day for day in review['days'] if day['submitted']]
    step_values = [
        int(day['steps'])
        for day in submitted_days
        if day.get('steps') is not None
    ]
    weight_points = [
        (day['date'], float(day['weight_kg']))
        for day in submitted_days
        if day.get('weight_kg') is not None
    ]

    action_rows = []
    target_total = 0
    achieved_total = 0
    for action in review['actions']:
        target = action.get('target_count') or action.get('eligible_days') or 0
        completed = action.get('completed_count') or 0
        target = int(target)
        completed = int(completed)
        target_total += target
        achieved_total += min(completed, target) if target else completed
        action_rows.append({
            'name': action.get('action_name'),
            'completed': completed,
            'target': target,
            'unit': action.get('target_unit') or '',
            'percent': round((completed / target) * 100) if target else 0,
        })

    measurement = review['measurements'][0] if review['measurements'] else None
    previous_measurement = get_previous_measurement_before(client_id, week_start)

    measurement_changes = []
    if measurement and previous_measurement:
        fields = [
            ('waist_cm', 'Waist'),
            ('lower_abdomen_cm', 'Lower abdomen'),
            ('hip_cm', 'Hip'),
        ]
        for key, label in fields:
            current = measurement.get(key)
            previous = previous_measurement.get(key)
            if current is not None and previous is not None:
                measurement_changes.append({
                    'label': label,
                    'change': round(float(current) - float(previous), 1),
                })

    attention = []
    if review['submitted_count'] < 5:
        attention.append(f"Only {review['submitted_count']}/7 daily check-ins submitted")
    if not measurement:
        attention.append('Weekly measurements are still due')
    low_actions = [row for row in action_rows if row['target'] and row['percent'] < 60]
    if low_actions:
        attention.append(
            'Low completion: ' + ', '.join(row['name'] for row in low_actions[:2])
        )

    client_notes = [
        {
            "date": day["date"],
            "note": day["note"],
        }
        for day in submitted_days
        if day.get("note")
    ]

    top_focus = []
    if attention:
        top_focus.extend(attention[:2])
    elif action_rows:
        strongest = sorted(
            action_rows,
            key=lambda row: row["percent"],
            reverse=True,
        )[0]
        top_focus.append(
            f"Build on: {strongest['name']} ({strongest['completed']}/{strongest['target']})"
        )
    else:
        top_focus.append("Use the call to establish the next clear focus")

    if client_notes:
        top_focus.append("Client left a note that may need discussion")

    return {
        'submitted_count': review['submitted_count'],
        'action_rows': action_rows,
        'action_percent': round((achieved_total / target_total) * 100) if target_total else 0,
        'average_steps': round(sum(step_values) / len(step_values)) if step_values else None,
        'weight_first': weight_points[0][1] if weight_points else None,
        'weight_latest': weight_points[-1][1] if weight_points else None,
        'weight_change': round(weight_points[-1][1] - weight_points[0][1], 1) if len(weight_points) >= 2 else None,
        'measurement': measurement,
        'measurement_changes': measurement_changes,
        'attention': attention,
        'client_notes': client_notes,
        'top_focus': top_focus,
    }
