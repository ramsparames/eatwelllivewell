import secrets
from datetime import date

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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_action_daily_logs (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id) ON DELETE CASCADE,
                    action_id INTEGER NOT NULL
                        REFERENCES client_action_plans(id) ON DELETE CASCADE,
                    tracked_on DATE NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (action_id, tracked_on)
                )
            """)

            # Older portal builds pointed action_id at a legacy client_actions
            # table. The coach workspace actually stores assignments in
            # client_action_plans, so keep the FK aligned with that source.
            cursor.execute("""
                ALTER TABLE client_action_daily_logs
                DROP CONSTRAINT IF EXISTS client_action_daily_logs_action_id_fkey
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
                       c.program, c.status,
                       p.access_token, p.enabled
                FROM client_portal_access p
                JOIN clients c ON c.id = p.client_id
                WHERE p.access_token = %s
                  AND p.enabled = TRUE
                LIMIT 1
            """, (access_token,))
            return cursor.fetchone()


def get_active_actions(client_id: int):
    """Return the same active assignments shown in the coach workspace.

    ClientService.actions() reads from client_action_plans. Those row ids are
    already the assignment ids that client_action_daily_logs must reference,
    so no catalog-id resolution is needed here.
    """
    actions = ClientService.actions(
        client_id,
        status="active",
    )

    return [dict(action) for action in actions]


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
                SELECT client_id, tracked_on, steps, weight_kg, note
                FROM client_daily_tracking
                WHERE client_id = %s
                  AND tracked_on = %s
                LIMIT 1
            """, (client_id, tracked_on))
            return cursor.fetchone()


def save_client_daily_entry(
    client_id: int,
    tracked_on: date,
    steps: int | None,
    weight_kg: float | None,
    note: str | None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO client_daily_tracking (
                    client_id, tracked_on, steps, weight_kg, note
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id, tracked_on)
                DO UPDATE SET
                    steps = COALESCE(
                        EXCLUDED.steps,
                        client_daily_tracking.steps
                    ),
                    weight_kg = COALESCE(
                        EXCLUDED.weight_kg,
                        client_daily_tracking.weight_kg
                    ),
                    note = COALESCE(
                        EXCLUDED.note,
                        client_daily_tracking.note
                    ),
                    updated_at = NOW()
            """, (
                client_id,
                tracked_on,
                steps,
                weight_kg,
                note,
            ))


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


def get_week_completion(client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE completed = TRUE
                    ) AS completed
                FROM client_action_daily_logs
                WHERE client_id = %s
                  AND tracked_on >= CURRENT_DATE - INTERVAL '6 days'
            """, (client_id,))
            row = cursor.fetchone()

    total = int(row["total"] or 0)
    completed = int(row["completed"] or 0)
    percent = round((completed / total) * 100) if total else 0

    return {
        "total": total,
        "completed": completed,
        "percent": percent,
    }
