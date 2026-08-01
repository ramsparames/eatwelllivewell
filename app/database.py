import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")


def get_connection():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    )


def create_database() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshot_submissions (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    answers JSONB NOT NULL,

                    total_score INTEGER NOT NULL,

                    recovery INTEGER NOT NULL,
                    metabolic INTEGER NOT NULL,
                    nutrition INTEGER NOT NULL,
                    behaviour INTEGER NOT NULL,
                    confidence INTEGER NOT NULL,

                    opportunity TEXT NOT NULL,
                    strength TEXT NOT NULL,

                    body_profile TEXT,
                    feeling TEXT,

                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )


def save_snapshot(
    name: str,
    phone: str,
    answers: dict[str, str],
    result: dict[str, Any],
) -> int:
    dimensions = result["dimensions"]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO snapshot_submissions (
                    name,
                    phone,
                    answers,

                    total_score,

                    recovery,
                    metabolic,
                    nutrition,
                    behaviour,
                    confidence,

                    opportunity,
                    strength,

                    body_profile,
                    feeling
                )
                VALUES (
                    %s, %s, %s,
                    %s,
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s
                )
                RETURNING id
                """,
                (
                    name,
                    phone,
                    json.dumps(answers),

                    result["total"],

                    dimensions["recovery"],
                    dimensions["metabolic"],
                    dimensions["nutrition"],
                    dimensions["behaviour"],
                    dimensions["confidence"],

                    result["opportunity"],
                    result["strength"],

                    result.get("bodyProfile"),
                    result.get("feeling"),
                ),
            )

            row = cursor.fetchone()

            if not row:
                raise RuntimeError("Snapshot could not be saved")

            return int(row["id"])


def get_all_leads() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    phone,
                    total_score,
                    opportunity,
                    strength,
                    submitted_at
                FROM snapshot_submissions
                ORDER BY submitted_at DESC
                """
            )

            return cursor.fetchall()


def get_lead_by_id(lead_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM snapshot_submissions
                WHERE id = %s
                """,
                (lead_id,),
            )

            return cursor.fetchone()
