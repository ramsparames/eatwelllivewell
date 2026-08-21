from __future__ import annotations

from datetime import date

from app.database import get_connection


def create_coaching_workflow_tables():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_weekly_reflections (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    week_start DATE NOT NULL,
                    wins TEXT,
                    challenge TEXT,
                    energy_score INTEGER,
                    help_needed TEXT,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (client_id, week_start)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coach_weekly_feedback (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    week_start DATE NOT NULL,
                    client_feedback TEXT,
                    private_note TEXT,
                    checkin_id INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (client_id, week_start)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workout_action_sync (
                    id BIGSERIAL PRIMARY KEY,
                    assignment_id BIGINT NOT NULL
                        REFERENCES client_workout_assignments(id) ON DELETE CASCADE,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    action_id INTEGER NOT NULL,
                    tracked_on DATE NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (assignment_id, action_id, tracked_on)
                )
            """)


def get_weekly_reflection(client_id: int, week_start: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM client_weekly_reflections
                WHERE client_id = %s AND week_start = %s
                LIMIT 1
            """, (client_id, week_start))
            return cursor.fetchone()


def save_weekly_reflection(
    client_id: int,
    week_start: date,
    wins: str | None,
    challenge: str | None,
    energy_score: int | None,
    help_needed: str | None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO client_weekly_reflections (
                    client_id, week_start, wins, challenge,
                    energy_score, help_needed
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (client_id, week_start)
                DO UPDATE SET
                    wins = EXCLUDED.wins,
                    challenge = EXCLUDED.challenge,
                    energy_score = EXCLUDED.energy_score,
                    help_needed = EXCLUDED.help_needed,
                    updated_at = NOW()
            """, (
                client_id, week_start, wins, challenge,
                energy_score, help_needed,
            ))


def get_coach_weekly_feedback(client_id: int, week_start: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM coach_weekly_feedback
                WHERE client_id = %s AND week_start = %s
                LIMIT 1
            """, (client_id, week_start))
            return cursor.fetchone()


def save_coach_weekly_feedback(
    client_id: int,
    week_start: date,
    client_feedback: str | None,
    private_note: str | None,
    checkin_id: int | None = None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO coach_weekly_feedback (
                    client_id, week_start, client_feedback,
                    private_note, checkin_id
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id, week_start)
                DO UPDATE SET
                    client_feedback = EXCLUDED.client_feedback,
                    private_note = EXCLUDED.private_note,
                    checkin_id = COALESCE(EXCLUDED.checkin_id, coach_weekly_feedback.checkin_id),
                    updated_at = NOW()
            """, (
                client_id, week_start, client_feedback,
                private_note, checkin_id,
            ))


def _strength_action_for_date(client_id: int, tracked_on: date):
    """
    Find the movement commitment that represents completing strength workouts.
    Stable action_key wins; legacy/custom title matching is retained for old clients.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, action_name, action_key
                FROM client_action_plans
                WHERE client_id = %s
                  AND status = 'active'
                  AND start_date <= %s
                  AND (end_date IS NULL OR end_date >= %s)
                  AND (
                    action_key = 'movement_advanced_strength_three'
                    OR LOWER(action_name) LIKE '%%strength%%workout%%'
                  )
                ORDER BY
                    CASE
                      WHEN action_key = 'movement_advanced_strength_three' THEN 0
                      ELSE 1
                    END,
                    id DESC
                LIMIT 1
            """, (client_id, tracked_on, tracked_on))
            return cursor.fetchone()


def sync_strength_action_from_workout(
    assignment_id: int,
    client_id: int,
    workout_date: date,
):
    """
    Completing an assigned workout automatically counts as that day's completion
    of a strength-workout action, if such an action exists for the date.

    If the client had already ticked the action manually, we leave it alone and
    do not create a sync ownership row.
    """
    action = _strength_action_for_date(client_id, workout_date)
    if not action:
        return None

    action_id = action["id"]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT completed
                FROM client_action_daily_logs
                WHERE action_id = %s AND tracked_on = %s
                LIMIT 1
            """, (action_id, workout_date))
            existing = cursor.fetchone()

            if existing and existing.get("completed"):
                return action_id

            cursor.execute("""
                INSERT INTO client_action_daily_logs (
                    client_id, action_id, tracked_on, completed
                )
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (action_id, tracked_on)
                DO UPDATE SET
                    completed = TRUE,
                    updated_at = NOW()
            """, (client_id, action_id, workout_date))

            cursor.execute("""
                INSERT INTO workout_action_sync (
                    assignment_id, client_id, action_id, tracked_on
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (assignment_id, action_id, tracked_on)
                DO NOTHING
            """, (assignment_id, client_id, action_id, workout_date))

    return action_id


def unsync_strength_action_from_workout(
    assignment_id: int,
    client_id: int,
):
    """
    Reopening a workout reverses only an action completion that this workout
    itself created. Manually-completed action logs are never removed.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT action_id, tracked_on
                FROM workout_action_sync
                WHERE assignment_id = %s AND client_id = %s
            """, (assignment_id, client_id))
            rows = cursor.fetchall() or []

            for row in rows:
                cursor.execute("""
                    UPDATE client_action_daily_logs
                    SET completed = FALSE,
                        updated_at = NOW()
                    WHERE action_id = %s
                      AND tracked_on = %s
                """, (row["action_id"], row["tracked_on"]))

            cursor.execute("""
                DELETE FROM workout_action_sync
                WHERE assignment_id = %s AND client_id = %s
            """, (assignment_id, client_id))


def ensure_week_actions_carried_forward(
    client_id: int,
    week_start: date,
    week_end: date,
) -> dict:
    """
    Standing-plan behavior.

    If this exact coaching week already has an active action plan, do nothing.
    Otherwise copy the most recent previous week's active actions, preserving
    action identity and targets.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)::int AS count
                FROM client_action_plans
                WHERE client_id = %s
                  AND start_date = %s
                  AND end_date = %s
                  AND status = 'active'
            """, (client_id, week_start, week_end))
            current = cursor.fetchone() or {"count": 0}
            if int(current.get("count") or 0) > 0:
                return {"created": 0, "reason": "week_already_has_plan"}

            cursor.execute("""
                SELECT MAX(start_date) AS source_week_start
                FROM client_action_plans
                WHERE client_id = %s
                  AND status = 'active'
                  AND start_date < %s
            """, (client_id, week_start))
            source = cursor.fetchone() or {}
            source_week_start = source.get("source_week_start")
            if source_week_start is None:
                return {"created": 0, "reason": "no_previous_plan"}

            cursor.execute("""
                SELECT action_name, action_key, target_count, target_unit
                FROM client_action_plans
                WHERE client_id = %s
                  AND status = 'active'
                  AND start_date = %s
                ORDER BY id
            """, (client_id, source_week_start))
            rows = cursor.fetchall() or []

            created = 0
            for row in rows:
                cursor.execute("""
                    INSERT INTO client_action_plans (
                        client_id, action_name, action_key,
                        target_count, target_unit,
                        start_date, end_date, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                """, (
                    client_id,
                    row["action_name"],
                    row.get("action_key"),
                    row.get("target_count"),
                    row.get("target_unit"),
                    week_start,
                    week_end,
                ))
                created += 1

            return {
                "created": created,
                "reason": "carried_forward",
                "source_week_start": source_week_start,
            }


def replace_future_week_action_plan(
    client_id: int,
    week_start: date,
    week_end: date,
) -> bool:
    """
    Make Sushma's explicitly saved Weekly Check-in plan authoritative.

    Future plans can be rebuilt safely only while no action logs exist.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM client_action_plans p
                JOIN client_action_daily_logs l
                  ON l.action_id = p.id
                WHERE p.client_id = %s
                  AND p.start_date = %s
                  AND p.end_date = %s
                LIMIT 1
            """, (client_id, week_start, week_end))
            if cursor.fetchone():
                return False

            cursor.execute("""
                DELETE FROM client_action_plans
                WHERE client_id = %s
                  AND start_date = %s
                  AND end_date = %s
            """, (client_id, week_start, week_end))
            return True


def get_client_coaching_history(client_id: int, limit: int = 24) -> list[dict]:
    """
    Combined client-visible coaching history by week.
    Private coach notes are intentionally excluded.
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(f.week_start, r.week_start) AS week_start,
                    f.client_feedback,
                    r.wins,
                    r.challenge,
                    r.energy_score,
                    r.help_needed,
                    r.submitted_at
                FROM coach_weekly_feedback f
                FULL OUTER JOIN client_weekly_reflections r
                  ON r.client_id = f.client_id
                 AND r.week_start = f.week_start
                WHERE COALESCE(f.client_id, r.client_id) = %s
                ORDER BY COALESCE(f.week_start, r.week_start) DESC
                LIMIT %s
            """, (client_id, limit))
            return cursor.fetchall() or []
