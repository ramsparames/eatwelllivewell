from __future__ import annotations

from datetime import date

from app.database import get_connection


def ensure_milestone_reviews_table() -> None:
    """Create the milestone review table non-destructively."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_milestone_reviews (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                    review_date DATE NOT NULL,
                    milestone_label TEXT NOT NULL,
                    biggest_wins TEXT,
                    improvements TEXT,
                    struggles TEXT,
                    nutrition_score INTEGER,
                    movement_score INTEGER,
                    sleep_score INTEGER,
                    confidence_score INTEGER,
                    next_focus TEXT,
                    coach_notes TEXT,
                    next_review_date DATE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_milestone_reviews_client_date
                ON client_milestone_reviews (client_id, review_date DESC, id DESC)
                """
            )
        connection.commit()


def list_milestone_reviews(client_id: int) -> list[dict]:
    ensure_milestone_reviews_table()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM client_milestone_reviews
                WHERE client_id = %s
                ORDER BY review_date DESC, id DESC
                """,
                (client_id,),
            )
            return [dict(row) for row in cursor.fetchall()]


def get_milestone_review(client_id: int, review_id: int) -> dict | None:
    ensure_milestone_reviews_table()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM client_milestone_reviews
                WHERE client_id = %s AND id = %s
                LIMIT 1
                """,
                (client_id, review_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None


def save_milestone_review(
    *,
    client_id: int,
    review_id: int | None,
    review_date: date,
    milestone_label: str,
    biggest_wins: str | None,
    improvements: str | None,
    struggles: str | None,
    nutrition_score: int | None,
    movement_score: int | None,
    sleep_score: int | None,
    confidence_score: int | None,
    next_focus: str | None,
    coach_notes: str | None,
    next_review_date: date | None,
) -> int:
    ensure_milestone_reviews_table()

    def clean_text(value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def clean_score(value: int | None) -> int | None:
        if value is None:
            return None
        return max(1, min(5, int(value)))

    milestone_label = (milestone_label or "Milestone Review").strip() or "Milestone Review"

    with get_connection() as connection:
        with connection.cursor() as cursor:
            if review_id:
                cursor.execute(
                    """
                    UPDATE client_milestone_reviews
                    SET review_date = %s,
                        milestone_label = %s,
                        biggest_wins = %s,
                        improvements = %s,
                        struggles = %s,
                        nutrition_score = %s,
                        movement_score = %s,
                        sleep_score = %s,
                        confidence_score = %s,
                        next_focus = %s,
                        coach_notes = %s,
                        next_review_date = %s,
                        updated_at = NOW()
                    WHERE id = %s AND client_id = %s
                    RETURNING id
                    """,
                    (
                        review_date,
                        milestone_label,
                        clean_text(biggest_wins),
                        clean_text(improvements),
                        clean_text(struggles),
                        clean_score(nutrition_score),
                        clean_score(movement_score),
                        clean_score(sleep_score),
                        clean_score(confidence_score),
                        clean_text(next_focus),
                        clean_text(coach_notes),
                        next_review_date,
                        review_id,
                        client_id,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError("Milestone review not found")
                saved_id = row["id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO client_milestone_reviews (
                        client_id, review_date, milestone_label,
                        biggest_wins, improvements, struggles,
                        nutrition_score, movement_score, sleep_score, confidence_score,
                        next_focus, coach_notes, next_review_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        client_id,
                        review_date,
                        milestone_label,
                        clean_text(biggest_wins),
                        clean_text(improvements),
                        clean_text(struggles),
                        clean_score(nutrition_score),
                        clean_score(movement_score),
                        clean_score(sleep_score),
                        clean_score(confidence_score),
                        clean_text(next_focus),
                        clean_text(coach_notes),
                        next_review_date,
                    ),
                )
                saved_id = cursor.fetchone()["id"]

        connection.commit()
        return saved_id
