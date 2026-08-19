from datetime import date
from typing import Any

from app.database import get_connection


def create_workout_tables() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coach_workouts (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL DEFAULT 'Strength',
                    duration_minutes INTEGER,
                    equipment TEXT,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workout_exercises (
                    id BIGSERIAL PRIMARY KEY,
                    workout_id BIGINT NOT NULL
                        REFERENCES coach_workouts(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    video_url TEXT,
                    sets INTEGER NOT NULL DEFAULT 3,
                    reps_text TEXT,
                    rest_seconds INTEGER,
                    instructions TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workout_exercises_workout
                ON workout_exercises(workout_id, position, id)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_workout_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id) ON DELETE CASCADE,
                    workout_id BIGINT NOT NULL
                        REFERENCES coach_workouts(id) ON DELETE CASCADE,
                    assigned_on DATE NOT NULL DEFAULT CURRENT_DATE,
                    due_date DATE,
                    coach_note TEXT,
                    status TEXT NOT NULL DEFAULT 'assigned',
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_client_workouts_client
                ON client_workout_assignments(client_id, assigned_on DESC)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_workout_set_logs (
                    id BIGSERIAL PRIMARY KEY,
                    assignment_id BIGINT NOT NULL
                        REFERENCES client_workout_assignments(id) ON DELETE CASCADE,
                    exercise_id BIGINT NOT NULL
                        REFERENCES workout_exercises(id) ON DELETE CASCADE,
                    set_number INTEGER NOT NULL,
                    weight_kg NUMERIC(8,2),
                    reps INTEGER,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (assignment_id, exercise_id, set_number)
                )
            """)


def _optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def create_workout(
    title: str,
    description: str | None,
    category: str,
    duration_minutes: int | None,
    equipment: str | None,
    exercises: list[dict[str, Any]],
) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO coach_workouts (
                    title, description, category, duration_minutes, equipment
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (title, description, category or "Strength", duration_minutes, equipment))
            workout_id = int(cursor.fetchone()["id"])

            for position, exercise in enumerate(exercises, start=1):
                name = (exercise.get("title") or "").strip()
                if not name:
                    continue
                cursor.execute("""
                    INSERT INTO workout_exercises (
                        workout_id, position, title, video_url,
                        sets, reps_text, rest_seconds, instructions
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    workout_id,
                    position,
                    name,
                    (exercise.get("video_url") or "").strip() or None,
                    int(exercise.get("sets") or 3),
                    (exercise.get("reps_text") or "").strip() or None,
                    _optional_int(exercise.get("rest_seconds")),
                    (exercise.get("instructions") or "").strip() or None,
                ))
    return workout_id


def list_workouts(active_only: bool = True):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                    w.*,
                    COUNT(e.id)::int AS exercise_count
                FROM coach_workouts w
                LEFT JOIN workout_exercises e ON e.workout_id = w.id
            """
            if active_only:
                sql += " WHERE w.active = TRUE"
            sql += " GROUP BY w.id ORDER BY w.active DESC, w.created_at DESC"
            cursor.execute(sql)
            return cursor.fetchall() or []


def get_workout(workout_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM coach_workouts WHERE id = %s", (workout_id,))
            workout = cursor.fetchone()
            if not workout:
                return None
            cursor.execute("""
                SELECT *
                FROM workout_exercises
                WHERE workout_id = %s
                ORDER BY position, id
            """, (workout_id,))
            workout["exercises"] = cursor.fetchall() or []
            return workout


def archive_workout(workout_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE coach_workouts
                SET active = FALSE, updated_at = NOW()
                WHERE id = %s
            """, (workout_id,))


def assign_workout(
    workout_id: int,
    client_ids: list[int],
    due_date: date | None = None,
    coach_note: str | None = None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for client_id in client_ids:
                cursor.execute("""
                    INSERT INTO client_workout_assignments (
                        client_id, workout_id, due_date, coach_note, status
                    )
                    VALUES (%s, %s, %s, %s, 'assigned')
                """, (client_id, workout_id, due_date, coach_note))


def get_client_workouts(client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.id AS assignment_id,
                    a.assigned_on,
                    a.due_date,
                    a.coach_note,
                    a.status,
                    a.started_at,
                    a.completed_at,
                    w.id AS workout_id,
                    w.title,
                    w.description,
                    w.category,
                    w.duration_minutes,
                    w.equipment,
                    COUNT(e.id)::int AS exercise_count
                FROM client_workout_assignments a
                JOIN coach_workouts w ON w.id = a.workout_id
                LEFT JOIN workout_exercises e ON e.workout_id = w.id
                WHERE a.client_id = %s
                  AND w.active = TRUE
                GROUP BY a.id, w.id
                ORDER BY
                    CASE a.status
                        WHEN 'in_progress' THEN 1
                        WHEN 'assigned' THEN 2
                        ELSE 3
                    END,
                    a.assigned_on DESC,
                    a.id DESC
            """, (client_id,))
            return cursor.fetchall() or []


def get_client_workout_assignment(assignment_id: int, client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.*,
                    w.title,
                    w.description,
                    w.category,
                    w.duration_minutes,
                    w.equipment
                FROM client_workout_assignments a
                JOIN coach_workouts w ON w.id = a.workout_id
                WHERE a.id = %s
                  AND a.client_id = %s
                LIMIT 1
            """, (assignment_id, client_id))
            assignment = cursor.fetchone()
            if not assignment:
                return None

            cursor.execute("""
                SELECT *
                FROM workout_exercises
                WHERE workout_id = %s
                ORDER BY position, id
            """, (assignment["workout_id"],))
            exercises = cursor.fetchall() or []

            cursor.execute("""
                SELECT exercise_id, set_number, weight_kg, reps, completed
                FROM client_workout_set_logs
                WHERE assignment_id = %s
            """, (assignment_id,))
            logs = {
                (row["exercise_id"], row["set_number"]): row
                for row in (cursor.fetchall() or [])
            }

            for exercise in exercises:
                exercise["set_logs"] = []
                for set_number in range(1, int(exercise.get("sets") or 0) + 1):
                    log = logs.get((exercise["id"], set_number))
                    exercise["set_logs"].append({
                        "set_number": set_number,
                        "weight_kg": log.get("weight_kg") if log else None,
                        "reps": log.get("reps") if log else None,
                        "completed": bool(log.get("completed")) if log else False,
                    })

            assignment["exercises"] = exercises
            return assignment


def save_set_log(
    assignment_id: int,
    client_id: int,
    exercise_id: int,
    set_number: int,
    weight_kg: float | None,
    reps: int | None,
    completed: bool,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1
                FROM client_workout_assignments a
                JOIN workout_exercises e ON e.workout_id = a.workout_id
                WHERE a.id = %s AND a.client_id = %s AND e.id = %s
            """, (assignment_id, client_id, exercise_id))
            if not cursor.fetchone():
                return False

            cursor.execute("""
                INSERT INTO client_workout_set_logs (
                    assignment_id, exercise_id, set_number,
                    weight_kg, reps, completed
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (assignment_id, exercise_id, set_number)
                DO UPDATE SET
                    weight_kg = EXCLUDED.weight_kg,
                    reps = EXCLUDED.reps,
                    completed = EXCLUDED.completed,
                    updated_at = NOW()
            """, (
                assignment_id, exercise_id, set_number,
                weight_kg, reps, completed,
            ))
            cursor.execute("""
                UPDATE client_workout_assignments
                SET status = CASE WHEN status = 'completed' THEN status ELSE 'in_progress' END,
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW()
                WHERE id = %s AND client_id = %s
            """, (assignment_id, client_id))
            return True


def complete_workout(assignment_id: int, client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE client_workout_assignments
                SET status = 'completed',
                    started_at = COALESCE(started_at, NOW()),
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s AND client_id = %s
            """, (assignment_id, client_id))


def reopen_workout(assignment_id: int, client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE client_workout_assignments
                SET status = 'in_progress',
                    completed_at = NULL,
                    updated_at = NOW()
                WHERE id = %s AND client_id = %s
            """, (assignment_id, client_id))


def get_coach_workout_assignment(assignment_id: int, client_id: int):
    """
    Coach-side workout detail including exercise prescriptions and the
    client's recorded weight/reps for every set.
    """
    return get_client_workout_assignment(assignment_id, client_id)


def get_workout_assignment_progress(assignment_id: int, client_id: int):
    assignment = get_client_workout_assignment(assignment_id, client_id)
    if not assignment:
        return None

    total_sets = 0
    completed_sets = 0

    for exercise in assignment.get("exercises") or []:
        for setlog in exercise.get("set_logs") or []:
            total_sets += 1
            if setlog.get("completed"):
                completed_sets += 1

    assignment["total_sets"] = total_sets
    assignment["completed_sets"] = completed_sets
    assignment["completion_percent"] = (
        round((completed_sets / total_sets) * 100)
        if total_sets
        else 0
    )
    return assignment
