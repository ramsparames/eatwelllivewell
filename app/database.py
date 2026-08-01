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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transformation_applications (
                    id BIGSERIAL PRIMARY KEY,
            
                    snapshot_id BIGINT REFERENCES snapshot_submissions(id)
                        ON DELETE SET NULL,
            
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    age_range TEXT NOT NULL,
            
                    why_now TEXT NOT NULL,
                    tried TEXT NOT NULL,
                    success_goal TEXT NOT NULL,
                    support_needed TEXT NOT NULL,
            
                    consent BOOLEAN NOT NULL DEFAULT FALSE,
            
                    status TEXT NOT NULL DEFAULT 'new',
                    coach_notes TEXT,
            
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
                    s.id AS snapshot_id,
                    s.name,
                    s.phone,
                    s.total_score,
                    s.opportunity,
                    s.strength,
                    s.submitted_at AS assessment_submitted_at,

                    a.id AS application_id,
                    a.email,
                    a.age_range,
                    a.status,
                    a.submitted_at AS application_submitted_at,

                    CASE
                        WHEN a.id IS NOT NULL THEN TRUE
                        ELSE FALSE
                    END AS has_application

                FROM snapshot_submissions AS s

                LEFT JOIN LATERAL (
                    SELECT *
                    FROM transformation_applications
                    WHERE snapshot_id = s.id
                    ORDER BY submitted_at DESC
                    LIMIT 1
                ) AS a ON TRUE

                ORDER BY
                    COALESCE(
                        a.submitted_at,
                        s.submitted_at
                    ) DESC
                """
            )

            assessment_leads = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    NULL::BIGINT AS snapshot_id,
                    a.name,
                    a.phone,
                    NULL::INTEGER AS total_score,
                    NULL::TEXT AS opportunity,
                    NULL::TEXT AS strength,
                    NULL::TIMESTAMPTZ AS assessment_submitted_at,

                    a.id AS application_id,
                    a.email,
                    a.age_range,
                    a.status,
                    a.submitted_at AS application_submitted_at,

                    TRUE AS has_application

                FROM transformation_applications AS a

                WHERE a.snapshot_id IS NULL

                ORDER BY a.submitted_at DESC
                """
            )

            application_only_leads = cursor.fetchall()

            combined = assessment_leads + application_only_leads

            combined.sort(
                key=lambda lead:
                    lead["application_submitted_at"]
                    or lead["assessment_submitted_at"],
                reverse=True,
            )

            return combined

def get_lead_profile(
    snapshot_id: int | None = None,
    application_id: int | None = None,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:

            if snapshot_id is not None:
                cursor.execute(
                    """
                    SELECT
                        s.*,

                        a.id AS application_id,
                        a.email,
                        a.age_range,
                        a.why_now,
                        a.tried,
                        a.success_goal,
                        a.support_needed,
                        a.consent,
                        a.status,
                        a.coach_notes,
                        a.submitted_at AS application_submitted_at,
                        a.updated_at AS application_updated_at

                    FROM snapshot_submissions AS s

                    LEFT JOIN LATERAL (
                        SELECT *
                        FROM transformation_applications
                        WHERE snapshot_id = s.id
                        ORDER BY submitted_at DESC
                        LIMIT 1
                    ) AS a ON TRUE

                    WHERE s.id = %s
                    """,
                    (snapshot_id,),
                )

                return cursor.fetchone()

            if application_id is not None:
                cursor.execute(
                    """
                    SELECT
                        s.*,

                        a.id AS application_id,
                        a.name AS application_name,
                        a.email,
                        a.phone AS application_phone,
                        a.age_range,
                        a.why_now,
                        a.tried,
                        a.success_goal,
                        a.support_needed,
                        a.consent,
                        a.status,
                        a.coach_notes,
                        a.submitted_at AS application_submitted_at,
                        a.updated_at AS application_updated_at

                    FROM transformation_applications AS a

                    LEFT JOIN snapshot_submissions AS s
                        ON s.id = a.snapshot_id

                    WHERE a.id = %s
                    """,
                    (application_id,),
                )

                row = cursor.fetchone()

                if row and row.get("id") is None:
                    row["name"] = row["application_name"]
                    row["phone"] = row["application_phone"]

                return row

            return None

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
def save_application(
    name: str,
    email: str,
    phone: str,
    age_range: str,
    why_now: str,
    tried: str,
    success_goal: str,
    support_needed: str,
    consent: bool,
) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:

            # Link the application to the most recent assessment
            # submitted with the same phone number.
            cursor.execute(
                """
                SELECT id
                FROM snapshot_submissions
                WHERE phone = %s
                ORDER BY submitted_at DESC
                LIMIT 1
                """,
                (phone,),
            )

            snapshot = cursor.fetchone()
            snapshot_id = snapshot["id"] if snapshot else None

            cursor.execute(
                """
                INSERT INTO transformation_applications (
                    snapshot_id,
                    name,
                    email,
                    phone,
                    age_range,
                    why_now,
                    tried,
                    success_goal,
                    support_needed,
                    consent
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    snapshot_id,
                    name,
                    email,
                    phone,
                    age_range,
                    why_now,
                    tried,
                    success_goal,
                    support_needed,
                    consent,
                ),
            )

            row = cursor.fetchone()

            if not row:
                raise RuntimeError(
                    "Transformation application could not be saved"
                )

            return int(row["id"])
def get_all_applications() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    a.id,
                    a.snapshot_id,
                    a.name,
                    a.email,
                    a.phone,
                    a.age_range,
                    a.status,
                    a.submitted_at,

                    s.total_score,
                    s.opportunity,
                    s.strength
                FROM transformation_applications AS a
                LEFT JOIN snapshot_submissions AS s
                    ON s.id = a.snapshot_id
                ORDER BY a.submitted_at DESC
                """
            )

            return cursor.fetchall()


def get_application_by_id(
    application_id: int,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    a.*,

                    s.total_score,
                    s.recovery,
                    s.metabolic,
                    s.nutrition,
                    s.behaviour,
                    s.confidence,
                    s.opportunity,
                    s.strength,
                    s.body_profile,
                    s.feeling,
                    s.answers AS assessment_answers
                FROM transformation_applications AS a
                LEFT JOIN snapshot_submissions AS s
                    ON s.id = a.snapshot_id
                WHERE a.id = %s
                """,
                (application_id,),
            )

            return cursor.fetchone()
