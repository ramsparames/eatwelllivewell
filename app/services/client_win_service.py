from __future__ import annotations

from datetime import date

from app.database import get_connection

WIN_CATEGORIES = (
    "Nutrition",
    "Strength",
    "Movement",
    "Sleep",
    "Mindset",
    "Measurements",
    "Consistency",
    "Energy",
    "Other",
)


def ensure_client_wins_table() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_wins (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    win_date DATE NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Other',
                    title TEXT NOT NULL,
                    note TEXT,
                    visible_to_client BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_wins_client_date
                ON client_wins (client_id, win_date DESC, id DESC)
                """
            )
        connection.commit()


def list_client_wins(
    client_id: int,
    *,
    visible_only: bool = False,
    limit: int | None = None,
) -> list[dict]:
    ensure_client_wins_table()
    clauses = ["client_id = %s"]
    params: list = [client_id]
    if visible_only:
        clauses.append("visible_to_client = TRUE")

    sql = f"""
        SELECT id, client_id, win_date, category, title, note,
               visible_to_client, created_at, updated_at
        FROM client_wins
        WHERE {' AND '.join(clauses)}
        ORDER BY win_date DESC, id DESC
    """
    if limit is not None:
        sql += " LIMIT %s"
        params.append(max(1, int(limit)))

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return [dict(row) for row in cursor.fetchall()]


def save_client_win(
    *,
    client_id: int,
    win_date: date,
    category: str,
    title: str,
    note: str | None = None,
    visible_to_client: bool = True,
) -> int:
    ensure_client_wins_table()
    title = (title or "").strip()
    if not title:
        raise ValueError("Please add the win.")
    category = (category or "Other").strip()
    if category not in WIN_CATEGORIES:
        category = "Other"
    note = (note or "").strip() or None

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO client_wins (
                    client_id, win_date, category, title, note, visible_to_client
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (client_id, win_date, category, title, note, visible_to_client),
            )
            win_id = cursor.fetchone()["id"]
        connection.commit()
    return win_id


def delete_client_win(client_id: int, win_id: int) -> bool:
    ensure_client_wins_table()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM client_wins WHERE id = %s AND client_id = %s",
                (win_id, client_id),
            )
            deleted = cursor.rowcount > 0
        connection.commit()
    return deleted
