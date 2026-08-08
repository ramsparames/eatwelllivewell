import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from datetime import date
from datetime import date, timedelta
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

                    status TEXT NOT NULL DEFAULT 'new',
                    coach_notes TEXT,
                    follow_up_date DATE,
                    
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_events (
                    id BIGSERIAL PRIMARY KEY,
            
                    snapshot_id BIGINT REFERENCES snapshot_submissions(id)
                        ON DELETE CASCADE,
            
                    application_id BIGINT REFERENCES transformation_applications(id)
                        ON DELETE CASCADE,
            
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details TEXT,
            
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
                    CONSTRAINT lead_event_has_owner
                    CHECK (
                        snapshot_id IS NOT NULL
                        OR application_id IS NOT NULL
                    )
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
            cursor.execute(
                """
                ALTER TABLE transformation_applications
                ADD COLUMN IF NOT EXISTS application_data JSONB
                    NOT NULL DEFAULT '{}'::jsonb
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS clarity_call_appointments (
                    id BIGSERIAL PRIMARY KEY,
            
                    external_appointment_id TEXT NOT NULL UNIQUE,
                    calendar_id TEXT NOT NULL,
            
                    contact_id TEXT,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
            
                    appointment_status TEXT,
                    title TEXT,
                    meeting_location TEXT,
            
                    start_time TIMESTAMPTZ NOT NULL,
                    end_time TIMESTAMPTZ,
            
                    raw_payload JSONB NOT NULL,
            
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE snapshot_submissions
                ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'new'
                """
            )
            
            cursor.execute(
                """
                ALTER TABLE snapshot_submissions
                ADD COLUMN IF NOT EXISTS coach_notes TEXT
                """
            )
            
            cursor.execute(
                """
                ALTER TABLE snapshot_submissions
                ADD COLUMN IF NOT EXISTS follow_up_date DATE
                """
            )
            
            cursor.execute(
                """
                ALTER TABLE transformation_applications
                ADD COLUMN IF NOT EXISTS follow_up_date DATE
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
            
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
            
                    program TEXT
                        NOT NULL DEFAULT 'Transformation',
            
                    status TEXT
                        NOT NULL DEFAULT 'active',
            
                    start_date DATE,
                    end_date DATE,
            
                    primary_goal TEXT,
                    goal_weight_kg NUMERIC(6,2),
            
                    initial_weight_kg NUMERIC(6,2),
            
                    weekly_call_day INTEGER,
                    weekly_call_time TIME,
            
                    timezone TEXT
                        NOT NULL DEFAULT 'Asia/Kolkata',
            
                    created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
            
                    updated_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_weekly_checkins (
                    id SERIAL PRIMARY KEY,
            
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id)
                        ON DELETE CASCADE,
            
                    week_number INTEGER,
            
                    call_date DATE NOT NULL,
            
                    weight_kg NUMERIC(6,2),
            
                    stress_score INTEGER,
                    mood_score INTEGER,
            
                    next_call_date DATE,
                    next_call_time TIME,
            
                    created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
            
                    updated_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_action_plans (
                    id SERIAL PRIMARY KEY,
            
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id)
                        ON DELETE CASCADE,
            
                    checkin_id INTEGER
                        REFERENCES client_weekly_checkins(id)
                        ON DELETE SET NULL,
            
                    action_name TEXT NOT NULL,
            
                    target_count INTEGER,
            
                    target_unit TEXT,
            
                    start_date DATE NOT NULL,
            
                    end_date DATE,
            
                    status TEXT
                        NOT NULL DEFAULT 'active',
            
                    created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_daily_tracking (
                    id SERIAL PRIMARY KEY,
            
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id)
                        ON DELETE CASCADE,
            
                    tracked_on DATE NOT NULL,
            
                    protein BOOLEAN,
                    water BOOLEAN,
            
                    steps INTEGER,
            
                    strength_training BOOLEAN,
            
                    stress_score INTEGER,
                    mood_score INTEGER,
            
                    weight_kg NUMERIC(6,2),
            
                    note TEXT,
            
                    created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
            
                    updated_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
            
                    UNIQUE(client_id, tracked_on)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_intakes (
                    id SERIAL PRIMARY KEY,
            
                    client_id INTEGER NOT NULL UNIQUE
                        REFERENCES clients(id)
                        ON DELETE CASCADE,
            
                    intake_date DATE NOT NULL,
            
                    current_situation TEXT,
                    primary_goal TEXT,
                    secondary_goals TEXT,
            
                    goal_weight_kg NUMERIC(6,2),
            
                    coach_focus TEXT,
            
                    created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW(),
            
                    updated_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )
            
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS client_measurements (
                    id SERIAL PRIMARY KEY,
            
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id)
                        ON DELETE CASCADE,
            
                    checkin_id INTEGER
                        REFERENCES client_weekly_checkins(id)
                        ON DELETE SET NULL,
            
                    measured_on DATE NOT NULL,
            
                    weight_kg NUMERIC(6,2),
            
                    upper_arm NUMERIC(7,2),
                    chest NUMERIC(7,2),
                    waist NUMERIC(7,2),
                    lower_abdomen NUMERIC(7,2),
                    hip NUMERIC(7,2),
                    thigh NUMERIC(7,2),
            
                    measurement_unit TEXT
                        NOT NULL DEFAULT 'inches',
            
                    created_at TIMESTAMPTZ
                        NOT NULL DEFAULT NOW()
                )
                """
            )
                
            cursor.execute(
                """
                ALTER TABLE client_weekly_checkins
                ADD COLUMN IF NOT EXISTS wins TEXT
                """
            )
            
            cursor.execute(
                """
                ALTER TABLE client_weekly_checkins
                ADD COLUMN IF NOT EXISTS struggles TEXT
                """
            )
            
            cursor.execute(
                """
                ALTER TABLE client_weekly_checkins
                ADD COLUMN IF NOT EXISTS improvements_needed TEXT
                """
            )
            
            cursor.execute(
                """
                ALTER TABLE client_weekly_checkins
                ADD COLUMN IF NOT EXISTS coach_support TEXT
                """
            )
            
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_weekly_checkins_client_date
                ON client_weekly_checkins(
                    client_id,
                    call_date DESC
                )
                """
            )
            
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_action_plans_client
                ON client_action_plans(client_id)
                """
            )
            
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_daily_tracking_client_date
                ON client_daily_tracking(
                    client_id,
                    tracked_on DESC
                )
                """
            )
            
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_weekly_checkins_next_call
                ON client_weekly_checkins(
                    next_call_date
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_client_measurements_client_date
                ON client_measurements(
                    client_id,
                    measured_on DESC
                )
                """
            )
            
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_client_intakes_client
                ON client_intakes(client_id)
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
                    s.status,
                    s.follow_up_date,
                    s.coach_notes,
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
                    a.status,
                    a.follow_up_date,
                    a.coach_notes,            
                    NULL::TIMESTAMPTZ AS assessment_submitted_at,

                    a.id AS application_id,
                    a.email,
                    a.age_range,
                    a.status AS application_status,
                    a.follow_up_date AS application_follow_up_date,
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
                        a.status AS application_status,
                        a.coach_notes AS application_coach_notes,
                        a.follow_up_date AS application_follow_up_date,
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
                        a.follow_up_date,
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
    *,
    snapshot_id: int | None,
    name: str,
    email: str,
    phone: str,
    age_range: str,
    why_now: str,
    tried: str,
    success_goal: str,
    support_needed: str,
    consent: bool,
    application_data: dict[str, Any] | None = None,
) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            linked_snapshot_id = snapshot_id

            # First preference:
            # use the exact assessment ID sent from the browser.
            if linked_snapshot_id is not None:
                cursor.execute(
                    """
                    SELECT id
                    FROM snapshot_submissions
                    WHERE id = %s
                    """,
                    (linked_snapshot_id,),
                )

                if cursor.fetchone() is None:
                    linked_snapshot_id = None

            # Fallback:
            # if there is no valid assessment ID, match by phone.
            if linked_snapshot_id is None:
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

                if snapshot:
                    linked_snapshot_id = snapshot["id"]

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
                    consent,
                    application_data
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s
                )
                RETURNING id
                """,
                (
                    linked_snapshot_id,
                    name,
                    email,
                    phone,
                    age_range,
                    why_now,
                    tried,
                    success_goal,
                    support_needed,
                    consent,
                    json.dumps(application_data or {}),
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
def update_lead_crm(
    lead_type: str,
    lead_id: int,
    status: str,
    coach_notes: str | None,
    follow_up_date: str | None,
) -> bool:
    allowed_statuses = {
        "new",
        "contacted",
        "clarity_call_booked",
        "joined_foundations",
        "joined_transformation",
        "follow_up_later",
        "closed",
    }

    if status not in allowed_statuses:
        raise ValueError("Invalid lead status")

    if lead_type == "assessment":
        table_name = "snapshot_submissions"
        snapshot_id = lead_id
        application_id = None

    elif lead_type == "application":
        table_name = "transformation_applications"
        snapshot_id = None
        application_id = lead_id

    else:
        raise ValueError("Invalid lead type")

    clean_note = coach_notes.strip() if coach_notes else None
    new_follow_up = follow_up_date or None

    with get_connection() as connection:
        with connection.cursor() as cursor:

            # Read the lead's existing CRM values.
            cursor.execute(
                f"""
                SELECT
                    status,
                    coach_notes,
                    follow_up_date
                FROM {table_name}
                WHERE id = %s
                """,
                (lead_id,),
            )

            existing = cursor.fetchone()

            if not existing:
                return False

            old_status = existing["status"]
            old_follow_up = existing["follow_up_date"]

            # Save the latest values.
            # A blank note does not erase the previous stored note.
            cursor.execute(
                f"""
                UPDATE {table_name}
                SET
                    status = %s,
                    coach_notes = COALESCE(%s, coach_notes),
                    follow_up_date = %s
                WHERE id = %s
                """,
                (
                    status,
                    clean_note,
                    new_follow_up,
                    lead_id,
                ),
            )

            def create_event(
                *,
                event_type: str,
                title: str,
                details: str | None = None,
            ) -> None:
                cursor.execute(
                    """
                    INSERT INTO lead_events (
                        snapshot_id,
                        application_id,
                        event_type,
                        title,
                        details
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        snapshot_id,
                        application_id,
                        event_type,
                        title,
                        details,
                    ),
                )

            # Record a status event only when the status changed.
            if status != old_status:
                status_event_types = {
                    "clarity_call_booked": "clarity_call_booked",
                    "joined_foundations": "joined_foundations",
                    "joined_transformation": "joined_transformation",
                    "closed": "lead_closed",
                }

                status_titles = {
                    "new": "Lead moved to New",
                    "contacted": "Lead contacted",
                    "clarity_call_booked": "Clarity Call Booked",
                    "joined_foundations": "Joined Foundations",
                    "joined_transformation": "Joined Transformation",
                    "follow_up_later": "Follow-up Later",
                    "closed": "Lead closed",
                }

                previous_status = (
                    old_status.replace("_", " ").title()
                    if old_status
                    else "Not set"
                )

                create_event(
                    event_type=status_event_types.get(
                        status,
                        "status_changed",
                    ),
                    title=status_titles.get(
                        status,
                        "Lead status changed",
                    ),
                    details=f"Previous status: {previous_status}",
                )

            # Every new note becomes a permanent timeline entry.
            if clean_note:
                create_event(
                    event_type="coach_note",
                    title="Sushma added",
                    details=clean_note,
                )

            old_follow_up_text = (
                old_follow_up.isoformat()
                if old_follow_up
                else None
            )

            # Record only new, changed or removed follow-up dates.
            if new_follow_up != old_follow_up_text:
                if new_follow_up:
                    friendly_date = date.fromisoformat(
                        new_follow_up
                    ).strftime("%d %b %Y")

                    create_event(
                        event_type="follow_up",
                        title="Follow-up scheduled",
                        details=friendly_date,
                    )

                elif old_follow_up:
                    create_event(
                        event_type="follow_up",
                        title="Follow-up removed",
                        details=old_follow_up.strftime(
                            "%d %b %Y"
                        ),
                    )

            return True
def add_lead_event(
    *,
    snapshot_id: int | None = None,
    application_id: int | None = None,
    event_type: str,
    title: str,
    details: str | None = None,
) -> int:
    if snapshot_id is None and application_id is None:
        raise ValueError(
            "A timeline event requires a snapshot or application ID"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO lead_events (
                    snapshot_id,
                    application_id,
                    event_type,
                    title,
                    details
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    snapshot_id,
                    application_id,
                    event_type,
                    title,
                    details,
                ),
            )

            row = cursor.fetchone()

            if not row:
                raise RuntimeError("Timeline event could not be saved")

            return int(row["id"])

def get_lead_events(
    *,
    snapshot_id: int | None = None,
    application_id: int | None = None,
) -> list[dict[str, Any]]:
    if snapshot_id is None and application_id is None:
        return []

    conditions = []
    parameters = []

    if snapshot_id is not None:
        conditions.append("snapshot_id = %s")
        parameters.append(snapshot_id)

    if application_id is not None:
        conditions.append("application_id = %s")
        parameters.append(application_id)

    where_clause = " OR ".join(conditions)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    snapshot_id,
                    application_id,
                    event_type,
                    title,
                    details,
                    created_at
                FROM lead_events
                WHERE {where_clause}
                ORDER BY created_at DESC, id DESC
                """,
                tuple(parameters),
            )

            return cursor.fetchall()
def upsert_clarity_call_appointment(
    *,
    external_appointment_id: str,
    calendar_id: str,
    contact_id: str | None,
    name: str | None,
    email: str | None,
    phone: str | None,
    appointment_status: str | None,
    title: str | None,
    meeting_location: str | None,
    start_time: str,
    end_time: str | None,
    raw_payload: dict[str, Any],
) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO clarity_call_appointments (
                    external_appointment_id,
                    calendar_id,
                    contact_id,
                    name,
                    email,
                    phone,
                    appointment_status,
                    title,
                    meeting_location,
                    start_time,
                    end_time,
                    raw_payload
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (external_appointment_id)
                DO UPDATE SET
                    calendar_id = EXCLUDED.calendar_id,
                    contact_id = EXCLUDED.contact_id,
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    appointment_status = EXCLUDED.appointment_status,
                    title = EXCLUDED.title,
                    meeting_location = EXCLUDED.meeting_location,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    external_appointment_id,
                    calendar_id,
                    contact_id,
                    name,
                    email,
                    phone,
                    appointment_status,
                    title,
                    meeting_location,
                    start_time,
                    end_time,
                    json.dumps(raw_payload),
                ),
            )

            row = cursor.fetchone()

            if not row:
                raise RuntimeError(
                    "Clarity call appointment could not be saved"
                )

            return int(row["id"])


def get_clarity_calls_for_day(
    *,
    start_time: str,
    end_time: str,
) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    external_appointment_id,
                    calendar_id,
                    contact_id,
                    name,
                    email,
                    phone,
                    appointment_status,
                    title,
                    meeting_location,
                    start_time,
                    end_time
                FROM clarity_call_appointments
                WHERE
                    start_time >= %s
                    AND start_time < %s
                    AND COALESCE(appointment_status, '') NOT IN (
                        'cancelled',
                        'canceled'
                    )
                ORDER BY start_time ASC
                """,
                (
                    start_time,
                    end_time,
                ),
            )

            return cursor.fetchall()
def create_client(
    name,
    email=None,
    phone=None,
    program="Transformation",
):
    conn = get_connection()

    with conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO clients
                (
                    name,
                    email,
                    phone,
                    program
                )
                VALUES
                (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    name,
                    email,
                    phone,
                    program,
                ),
            )
            
            row = cursor.fetchone()
            
            if not row:
                raise RuntimeError(
                    "Client could not be created"
                )
            
            return int(row["id"])
def get_clients():
    conn = get_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT *
            FROM clients
            ORDER BY name
            """
        )

        return cursor.fetchall()

def get_client(client_id):
    conn = get_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT *
            FROM clients
            WHERE id=%s
            """,
            (client_id,),
        )

        return cursor.fetchone()
        
def create_weekly_checkin(
    client_id: int,
    call_date,
    weight_kg=None,
    stress_score=None,
    mood_score=None,
    next_call_date=None,
    next_call_time=None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO client_weekly_checkins (
                    client_id,
                    call_date,
                    weight_kg,
                    stress_score,
                    mood_score,
                    next_call_date,
                    next_call_time
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    client_id,
                    call_date,
                    weight_kg,
                    stress_score,
                    mood_score,
                    next_call_date,
                    next_call_time,
                ),
            )

            row = cursor.fetchone()
            return int(row["id"])


def get_client_checkins(client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM client_weekly_checkins
                WHERE client_id = %s
                ORDER BY call_date DESC, id DESC
                """,
                (client_id,),
            )

            return cursor.fetchall()


def get_calls_today():
    today = date.today()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id AS client_id,
                    c.name,
                    c.program,
                    w.next_call_date,
                    w.next_call_time
                FROM client_weekly_checkins w
                JOIN clients c
                    ON c.id = w.client_id
                WHERE
                    w.next_call_date = %s
                    AND c.status = 'active'
                ORDER BY
                    w.next_call_time NULLS LAST,
                    c.name
                """,
                (today,),
            )

            return cursor.fetchall()


def get_calls_this_week():
    today = date.today()
    end_of_week = today + timedelta(
        days=6 - today.weekday()
    )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id AS client_id,
                    c.name,
                    c.program,
                    w.next_call_date,
                    w.next_call_time
                FROM client_weekly_checkins w
                JOIN clients c
                    ON c.id = w.client_id
                WHERE
                    w.next_call_date BETWEEN %s AND %s
                    AND c.status = 'active'
                ORDER BY
                    w.next_call_date,
                    w.next_call_time NULLS LAST,
                    c.name
                """,
                (
                    today,
                    end_of_week,
                ),
            )

            return cursor.fetchall()
            
def get_client_summaries():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.email,
                    c.phone,
                    c.program,
                    c.status,
                    c.start_date,

                    latest.weight_kg
                        AS current_weight_kg,

                    latest.next_call_date,
                    latest.next_call_time

                FROM clients c

                LEFT JOIN LATERAL (
                    SELECT
                        w.weight_kg,
                        w.next_call_date,
                        w.next_call_time
                    FROM client_weekly_checkins w
                    WHERE w.client_id = c.id
                    ORDER BY
                        w.call_date DESC,
                        w.id DESC
                    LIMIT 1
                ) latest ON TRUE

                ORDER BY
                    CASE
                        WHEN c.status = 'active'
                        THEN 0
                        ELSE 1
                    END,
                    c.name
                """
            )

            return cursor.fetchall()
            
def create_client_action(
    client_id: int,
    action_name: str,
    target_count: int | None,
    target_unit: str | None,
    start_date,
    end_date=None,
    checkin_id=None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO client_action_plans (
                    client_id,
                    checkin_id,
                    action_name,
                    target_count,
                    target_unit,
                    start_date,
                    end_date
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    client_id,
                    checkin_id,
                    action_name,
                    target_count,
                    target_unit,
                    start_date,
                    end_date,
                ),
            )

            row = cursor.fetchone()

            if not row:
                raise RuntimeError(
                    "Client action could not be created"
                )

            return int(row["id"])


def get_client_actions(
    client_id: int,
    status: str | None = None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:

            if status:
                cursor.execute(
                    """
                    SELECT *
                    FROM client_action_plans
                    WHERE client_id = %s
                      AND status = %s
                    ORDER BY start_date DESC, id DESC
                    """,
                    (
                        client_id,
                        status,
                    ),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM client_action_plans
                    WHERE client_id = %s
                    ORDER BY start_date DESC, id DESC
                    """,
                    (client_id,),
                )

            return cursor.fetchall()


def complete_client_action(
    action_id: int,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE client_action_plans
                SET status = 'completed'
                WHERE id = %s
                """,
                (action_id,),
            )

def save_daily_tracking(
    client_id: int,
    tracked_on,
    protein: bool | None = None,
    water: bool | None = None,
    steps: int | None = None,
    strength_training: bool | None = None,
    stress_score: int | None = None,
    mood_score: int | None = None,
    weight_kg: float | None = None,
    note: str | None = None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO client_daily_tracking (
                    client_id,
                    tracked_on,
                    protein,
                    water,
                    steps,
                    strength_training,
                    stress_score,
                    mood_score,
                    weight_kg,
                    note
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (
                    client_id,
                    tracked_on
                )
                DO UPDATE SET
                    protein = EXCLUDED.protein,
                    water = EXCLUDED.water,

                    steps = COALESCE(
                        EXCLUDED.steps,
                        client_daily_tracking.steps
                    ),

                    strength_training =
                        EXCLUDED.strength_training,

                    stress_score = COALESCE(
                        EXCLUDED.stress_score,
                        client_daily_tracking.stress_score
                    ),

                    mood_score = COALESCE(
                        EXCLUDED.mood_score,
                        client_daily_tracking.mood_score
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

                RETURNING id
                """,
                (
                    client_id,
                    tracked_on,
                    protein,
                    water,
                    steps,
                    strength_training,
                    stress_score,
                    mood_score,
                    weight_kg,
                    note,
                ),
            )

            row = cursor.fetchone()

            if not row:
                raise RuntimeError(
                    "Daily tracking could not be saved"
                )

            return int(row["id"])
            

def get_client_tracking(
    client_id: int,
    start_date=None,
    end_date=None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:

            if start_date and end_date:
                cursor.execute(
                    """
                    SELECT *
                    FROM client_daily_tracking
                    WHERE client_id = %s
                      AND tracked_on
                          BETWEEN %s AND %s
                    ORDER BY tracked_on
                    """,
                    (
                        client_id,
                        start_date,
                        end_date,
                    ),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM client_daily_tracking
                    WHERE client_id = %s
                    ORDER BY tracked_on DESC
                    """,
                    (client_id,),
                )

            return cursor.fetchall()          
            
if __name__ == "__main__":
    create_database()
    print("Database updated successfully.")
