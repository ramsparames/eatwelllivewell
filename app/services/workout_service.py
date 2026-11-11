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
                ALTER TABLE client_workout_assignments
                ADD COLUMN IF NOT EXISTS workout_date DATE
            """)
            cursor.execute("""
                ALTER TABLE client_workout_assignments
                ADD COLUMN IF NOT EXISTS planned_week_start DATE
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_client_workouts_client
                ON client_workout_assignments(client_id, assigned_on DESC)
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_client_workout_assignment_active
                ON client_workout_assignments(client_id, workout_id)
                WHERE status IN ('assigned', 'in_progress', 'completed')
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_workout_exercise_notes (
                    id BIGSERIAL PRIMARY KEY,
                    assignment_id BIGINT NOT NULL
                        REFERENCES client_workout_assignments(id) ON DELETE CASCADE,
                    exercise_id BIGINT NOT NULL
                        REFERENCES workout_exercises(id) ON DELETE CASCADE,
                    client_note TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (assignment_id, exercise_id)
                )
            """)


            # Each use of an assigned workout is a separate session. Keep the
            # legacy set-log tables intact to preserve previously saved data.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_workout_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    assignment_id BIGINT NOT NULL REFERENCES client_workout_assignments(id) ON DELETE CASCADE,
                    workout_date DATE,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workout_sessions_assignment
                ON client_workout_sessions(assignment_id, id DESC)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_workout_open_session
                ON client_workout_sessions(assignment_id) WHERE completed_at IS NULL
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_workout_session_sets (
                    id BIGSERIAL PRIMARY KEY,
                    session_id BIGINT NOT NULL REFERENCES client_workout_sessions(id) ON DELETE CASCADE,
                    exercise_id BIGINT NOT NULL REFERENCES workout_exercises(id) ON DELETE CASCADE,
                    set_number INTEGER NOT NULL,
                    weight_kg NUMERIC(8,2),
                    reps INTEGER,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(session_id, exercise_id, set_number)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_workout_session_notes (
                    session_id BIGINT NOT NULL REFERENCES client_workout_sessions(id) ON DELETE CASCADE,
                    exercise_id BIGINT NOT NULL REFERENCES workout_exercises(id) ON DELETE CASCADE,
                    client_note TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY(session_id, exercise_id)
                )
            """)
            # One-time, idempotent import of existing workout history. Completed
            # assignments become completed sessions; in-progress logs stay editable.
            cursor.execute("""
                INSERT INTO client_workout_sessions
                    (assignment_id, workout_date, started_at, completed_at)
                SELECT a.id, a.workout_date,
                       COALESCE(a.started_at, a.created_at),
                       CASE WHEN a.status = 'completed'
                            THEN COALESCE(a.completed_at, a.updated_at) ELSE NULL END
                FROM client_workout_assignments a
                WHERE a.status <> 'removed'
                  AND NOT EXISTS (SELECT 1 FROM client_workout_sessions s WHERE s.assignment_id = a.id)
                  AND (a.status = 'completed' OR EXISTS (
                      SELECT 1 FROM client_workout_set_logs l WHERE l.assignment_id = a.id
                  ) OR EXISTS (
                      SELECT 1 FROM client_workout_exercise_notes n WHERE n.assignment_id = a.id
                  ))
            """)
            cursor.execute("""
                INSERT INTO client_workout_session_sets
                    (session_id, exercise_id, set_number, weight_kg, reps, completed, updated_at)
                SELECT s.id, l.exercise_id, l.set_number, l.weight_kg, l.reps, l.completed, l.updated_at
                FROM client_workout_set_logs l
                JOIN client_workout_sessions s ON s.assignment_id = l.assignment_id
                WHERE NOT EXISTS (SELECT 1 FROM client_workout_session_sets x WHERE x.session_id = s.id)
                  AND s.id = (SELECT MIN(id) FROM client_workout_sessions WHERE assignment_id = l.assignment_id)
                ON CONFLICT(session_id, exercise_id, set_number) DO NOTHING
            """)
            cursor.execute("""
                INSERT INTO client_workout_session_notes(session_id, exercise_id, client_note, updated_at)
                SELECT s.id, n.exercise_id, n.client_note, n.updated_at
                FROM client_workout_exercise_notes n
                JOIN client_workout_sessions s ON s.assignment_id = n.assignment_id
                WHERE s.id = (SELECT MIN(id) FROM client_workout_sessions WHERE assignment_id = n.assignment_id)
                ON CONFLICT(session_id, exercise_id) DO NOTHING
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
    coach_note: str | None = None,
    planned_week_start: date | None = None,
):
    """
    Assign a workout without a due date.

    planned_week_start records the coaching week Sushma intended this workout
    for. Older/manual assignments can leave it NULL.
    """
    created = 0
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for client_id in client_ids:
                # Avoid duplicate active assignment of the same workout for the
                # same planned week. If no week is supplied, retain legacy guard.
                if planned_week_start:
                    cursor.execute("""
                        SELECT id
                        FROM client_workout_assignments
                        WHERE client_id = %s
                          AND workout_id = %s
                          AND planned_week_start = %s
                          AND status <> 'removed'
                        LIMIT 1
                    """, (client_id, workout_id, planned_week_start))
                else:
                    cursor.execute("""
                        SELECT id
                        FROM client_workout_assignments
                        WHERE client_id = %s
                          AND workout_id = %s
                          AND status IN ('assigned', 'in_progress')
                        ORDER BY id DESC
                        LIMIT 1
                    """, (client_id, workout_id))

                if cursor.fetchone():
                    continue

                cursor.execute("""
                    INSERT INTO client_workout_assignments (
                        client_id, workout_id, coach_note,
                        planned_week_start, status
                    )
                    VALUES (%s, %s, %s, %s, 'assigned')
                """, (
                    client_id, workout_id, coach_note, planned_week_start,
                ))
                created += 1
    return created


def get_client_workouts(client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.id AS assignment_id,
                    a.assigned_on,
                    a.planned_week_start,
                    a.workout_date,
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
                    COUNT(DISTINCT e.id)::int AS exercise_count,
                    COUNT(DISTINCT sl.id) FILTER (WHERE sl.completed = TRUE)::int AS completed_sets,
                    COUNT(DISTINCT sl.id)::int AS logged_sets
                FROM client_workout_assignments a
                JOIN coach_workouts w ON w.id = a.workout_id
                LEFT JOIN workout_exercises e ON e.workout_id = w.id
                LEFT JOIN client_workout_sessions session
                    ON session.assignment_id = a.id AND session.completed_at IS NULL
                LEFT JOIN client_workout_session_sets sl ON sl.session_id = session.id
                WHERE a.client_id = %s
                  AND a.status <> 'removed'
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


def remove_workout_assignment(
    assignment_id: int,
    client_id: int,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE client_workout_assignments
                SET status = 'removed',
                    updated_at = NOW()
                WHERE id = %s
                  AND client_id = %s
            """, (assignment_id, client_id))


def _session_for_edit(cursor, assignment_id: int, client_id: int):
    """Lock the assignment so concurrent saves can't create two open sessions."""
    cursor.execute("""
        SELECT id FROM client_workout_assignments
        WHERE id = %s AND client_id = %s AND status <> 'removed' FOR UPDATE
    """, (assignment_id, client_id))
    if not cursor.fetchone():
        return None
    cursor.execute("""
        SELECT id FROM client_workout_sessions
        WHERE assignment_id = %s AND completed_at IS NULL
        ORDER BY id DESC LIMIT 1
    """, (assignment_id,))
    row = cursor.fetchone()
    if row:
        return row['id']
    cursor.execute("""
        INSERT INTO client_workout_sessions(assignment_id) VALUES (%s) RETURNING id
    """, (assignment_id,))
    return cursor.fetchone()['id']


def get_workout_session_history(assignment_id: int, client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT s.id, s.workout_date, s.completed_at, s.started_at,
                       e.id AS exercise_id, e.title AS exercise_title,
                       l.set_number, l.weight_kg, l.reps, l.completed,
                       n.client_note
                FROM client_workout_sessions s
                JOIN client_workout_assignments a ON a.id = s.assignment_id
                LEFT JOIN client_workout_session_sets l ON l.session_id = s.id
                LEFT JOIN workout_exercises e ON e.id = l.exercise_id
                LEFT JOIN client_workout_session_notes n
                    ON n.session_id = s.id AND n.exercise_id = e.id
                WHERE s.assignment_id = %s AND a.client_id = %s AND s.completed_at IS NOT NULL
                ORDER BY s.workout_date DESC NULLS LAST, s.id DESC, e.position, l.set_number
            """, (assignment_id, client_id))
            sessions = {}
            for r in cursor.fetchall() or []:
                session = sessions.setdefault(r['id'], {
                    'id': r['id'], 'date': r['workout_date'],
                    'completed_at': r['completed_at'], 'exercises': {}
                })
                if r['exercise_id'] is not None:
                    exercise = session['exercises'].setdefault(r['exercise_id'], {
                        'title': r['exercise_title'], 'notes': r['client_note'], 'sets': []
                    })
                    exercise['sets'].append({
                        'set_number': r['set_number'], 'weight_kg': r['weight_kg'],
                        'reps': r['reps'], 'completed': r['completed']
                    })
            return [dict(s, exercises=list(s['exercises'].values())) for s in sessions.values()]


def get_client_workout_assignment(assignment_id: int, client_id: int, coach_view: bool = False):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT a.*, w.title, w.description, w.category, w.duration_minutes, w.equipment
                FROM client_workout_assignments a
                JOIN coach_workouts w ON w.id = a.workout_id
                WHERE a.id = %s AND a.client_id = %s AND a.status <> 'removed' LIMIT 1
            """, (assignment_id, client_id))
            assignment = cursor.fetchone()
            if not assignment:
                return None
            cursor.execute("""
                SELECT * FROM workout_exercises
                WHERE workout_id = %s ORDER BY position, id
            """, (assignment['workout_id'],))
            exercises = cursor.fetchall() or []
            cursor.execute("""
                SELECT id, workout_date, completed_at FROM client_workout_sessions
                WHERE assignment_id = %s
                AND (%s OR completed_at IS NULL)
                ORDER BY (completed_at IS NULL) DESC, id DESC LIMIT 1
            """, (assignment_id, coach_view))
            session = cursor.fetchone()
            # A completed session is immutable. The client gets a clean form for
            # the next visit; the coach sees the latest completed log instead.
            session_id = session['id'] if session else None
            assignment['current_session_id'] = session_id if session and session['completed_at'] is None else None
            assignment['viewed_session_date'] = session['workout_date'] if session else None
            assignment['session_count'] = 0
            cursor.execute("""
                SELECT COUNT(*) AS total FROM client_workout_sessions
                WHERE assignment_id = %s AND completed_at IS NOT NULL
            """, (assignment_id,))
            assignment['session_count'] = cursor.fetchone()['total']
            logs = {}
            notes = {}
            if session_id:
                cursor.execute("""
                    SELECT exercise_id, set_number, weight_kg, reps, completed
                    FROM client_workout_session_sets WHERE session_id = %s
                """, (session_id,))
                logs = {(r['exercise_id'], r['set_number']): r for r in cursor.fetchall() or []}
                cursor.execute("""
                    SELECT exercise_id, client_note FROM client_workout_session_notes
                    WHERE session_id = %s
                """, (session_id,))
                notes = {r['exercise_id']: r['client_note'] for r in cursor.fetchall() or []}
            for exercise in exercises:
                exercise['client_note'] = notes.get(exercise['id'])
                exercise['set_logs'] = []
                for number in range(1, int(exercise.get('sets') or 0) + 1):
                    log = logs.get((exercise['id'], number))
                    exercise['set_logs'].append({
                        'set_number': number,
                        'weight_kg': log['weight_kg'] if log else None,
                        'reps': log['reps'] if log else None,
                        'completed': bool(log['completed']) if log else False,
                    })
            assignment['exercises'] = exercises
            return assignment


def save_set_log(assignment_id, client_id, exercise_id, set_number, weight_kg, reps, completed):
    return save_exercise_log(assignment_id, client_id, exercise_id, [dict(
        set_number=set_number, weight_kg=weight_kg, reps=reps, completed=completed
    )], preserve_other_sets=True)


def save_exercise_log(
    assignment_id: int, client_id: int, exercise_id: int,
    sets: list[dict], client_note: str | None = None,
    preserve_other_sets: bool = False,
):
    """Write an exercise's sets only into this assignment's current session."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.sets FROM client_workout_assignments a
                JOIN workout_exercises e ON e.workout_id = a.workout_id
                WHERE a.id = %s AND a.client_id = %s AND e.id = %s
                  AND a.status <> 'removed' LIMIT 1
            """, (assignment_id, client_id, exercise_id))
            exercise = cursor.fetchone()
            if not exercise:
                return False
            max_sets = int(exercise['sets'] or 0)
            parsed = []
            for item in sets:
                try:
                    number = int(item.get('set_number'))
                    if not 1 <= number <= max_sets:
                        continue
                    weight = item.get('weight_kg')
                    weight = None if weight in ('', None) else float(weight)
                    reps = item.get('reps')
                    reps = None if reps in ('', None) else int(reps)
                    if (weight is not None and (weight < 0 or weight > 999999)) or (reps is not None and (reps < 0 or reps > 100000)):
                        return False
                    parsed.append((number, weight, reps, bool(item.get('completed'))))
                except (TypeError, ValueError, OverflowError):
                    return False
            session_id = _session_for_edit(cursor, assignment_id, client_id)
            if session_id is None:
                return False
            for number, weight, reps, completed in parsed:
                cursor.execute("""
                    INSERT INTO client_workout_session_sets
                        (session_id, exercise_id, set_number, weight_kg, reps, completed)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id, exercise_id, set_number) DO UPDATE SET
                        weight_kg = EXCLUDED.weight_kg, reps = EXCLUDED.reps,
                        completed = EXCLUDED.completed, updated_at = NOW()
                """, (session_id, exercise_id, number, weight, reps, completed))
            if not preserve_other_sets:
                cursor.execute("""
                    INSERT INTO client_workout_session_notes(session_id, exercise_id, client_note)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(session_id, exercise_id) DO UPDATE SET
                        client_note = EXCLUDED.client_note, updated_at = NOW()
                """, (session_id, exercise_id, (client_note or '').strip() or None))
            cursor.execute("""
                UPDATE client_workout_assignments SET status = 'in_progress',
                    started_at = COALESCE(started_at, NOW()), updated_at = NOW()
                WHERE id = %s AND client_id = %s
            """, (assignment_id, client_id))
            return True


def complete_workout(assignment_id: int, client_id: int, workout_date: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            session_id = _session_for_edit(cursor, assignment_id, client_id)
            if session_id is None:
                return False
            cursor.execute("""
                UPDATE client_workout_sessions
                SET workout_date = %s, completed_at = NOW()
                WHERE id = %s AND completed_at IS NULL
            """, (workout_date, session_id))
            cursor.execute("""
                UPDATE client_workout_assignments SET status = 'completed',
                    workout_date = %s, completed_at = NOW(),
                    started_at = COALESCE(started_at, NOW()), updated_at = NOW()
                WHERE id = %s AND client_id = %s
            """, (workout_date, assignment_id, client_id))
            return True


def reopen_workout(assignment_id: int, client_id: int):
    """Legacy reopen action now starts a new session without erasing history."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            session_id = _session_for_edit(cursor, assignment_id, client_id)
            if session_id is None:
                return False
            cursor.execute("""
                UPDATE client_workout_assignments SET status = 'in_progress',
                    updated_at = NOW() WHERE id = %s AND client_id = %s
            """, (assignment_id, client_id))
            return True


def get_coach_workout_assignment(assignment_id: int, client_id: int):
    """
    Coach-side workout detail including exercise prescriptions and the
    client's recorded weight/reps for every set.
    """
    return get_client_workout_assignment(assignment_id, client_id, coach_view=True)


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
