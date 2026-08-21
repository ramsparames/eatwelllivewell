
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from app.database import get_connection


def _rows(sql: str, params=()):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()


def _row(sql: str, params=()):
    rows = _rows(sql, params)
    return rows[0] if rows else None


def get_client_weekly_summary(client_id: int, week_start: date | None = None) -> dict:
    """Factual weekly summary built only from data already captured in NourisHer."""
    if week_start is None:
        week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=6)

    daily = _rows("""
        SELECT tracked_on, steps, weight_kg
        FROM client_daily_tracking
        WHERE client_id = %s AND tracked_on BETWEEN %s AND %s
        ORDER BY tracked_on
    """, (client_id, week_start, week_end))

    action = _row("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE completed = TRUE) AS completed
        FROM client_action_daily_logs
        WHERE client_id = %s AND tracked_on BETWEEN %s AND %s
    """, (client_id, week_start, week_end)) or {"total": 0, "completed": 0}

    workouts = _row("""
        SELECT COUNT(*) AS assigned,
               COUNT(*) FILTER (WHERE status = 'completed') AS completed
        FROM client_workout_assignments
        WHERE client_id = %s
          AND assigned_on <= %s
          AND (workout_date BETWEEN %s AND %s OR status <> 'completed')
    """, (client_id, week_end, week_start, week_end)) or {"assigned": 0, "completed": 0}

    steps = [int(r["steps"]) for r in daily if r.get("steps") is not None]
    weights = [float(r["weight_kg"]) for r in daily if r.get("weight_kg") is not None]
    total = int(action.get("total") or 0)
    completed = int(action.get("completed") or 0)

    previous_start = week_start - timedelta(days=7)
    previous_end = week_start - timedelta(days=1)
    prev = _rows("""
        SELECT steps
        FROM client_daily_tracking
        WHERE client_id = %s AND tracked_on BETWEEN %s AND %s AND steps IS NOT NULL
    """, (client_id, previous_start, previous_end))
    prev_steps = [int(r["steps"]) for r in prev]
    step_change_pct = None
    if steps and prev_steps and mean(prev_steps):
        step_change_pct = round(((mean(steps) - mean(prev_steps)) / mean(prev_steps)) * 100)

    latest_checkin = _row("""
        SELECT call_date, wins, struggles, improvements_needed, coach_support
        FROM client_weekly_checkins
        WHERE client_id = %s
        ORDER BY call_date DESC, id DESC
        LIMIT 1
    """, (client_id,))

    return {
        "week_start": week_start,
        "week_end": week_end,
        "days_updated": len(daily),
        "avg_steps": round(mean(steps)) if steps else None,
        "step_change_pct": step_change_pct,
        "first_weight": weights[0] if weights else None,
        "latest_weight": weights[-1] if weights else None,
        "weight_change": round(weights[-1] - weights[0], 2) if len(weights) >= 2 else None,
        "action_total": total,
        "action_completed": completed,
        "action_percent": round(completed * 100 / total) if total else None,
        "workouts_assigned": int(workouts.get("assigned") or 0),
        "workouts_completed": int(workouts.get("completed") or 0),
        "latest_checkin": latest_checkin,
    }


def get_client_progress_charts(client_id: int, weeks: int = 12) -> dict:
    start = date.today() - timedelta(days=(weeks * 7) - 1)
    daily = _rows("""
        SELECT tracked_on, steps, weight_kg
        FROM client_daily_tracking
        WHERE client_id = %s AND tracked_on >= %s
        ORDER BY tracked_on
    """, (client_id, start))
    actions = _rows("""
        SELECT tracked_on, completed
        FROM client_action_daily_logs
        WHERE client_id = %s AND tracked_on >= %s
        ORDER BY tracked_on
    """, (client_id, start))
    workouts = _rows("""
        SELECT workout_date
        FROM client_workout_assignments
        WHERE client_id = %s AND status = 'completed'
          AND workout_date >= %s
        ORDER BY workout_date
    """, (client_id, start))

    buckets = defaultdict(lambda: {"steps": [], "action_total": 0, "action_done": 0, "workouts": 0})
    for r in daily:
        d = r["tracked_on"]
        ws = d - timedelta(days=d.weekday())
        if r.get("steps") is not None:
            buckets[ws]["steps"].append(int(r["steps"]))
    for r in actions:
        d = r["tracked_on"]
        ws = d - timedelta(days=d.weekday())
        buckets[ws]["action_total"] += 1
        buckets[ws]["action_done"] += 1 if r.get("completed") else 0
    for r in workouts:
        d = r["workout_date"]
        ws = d - timedelta(days=d.weekday())
        buckets[ws]["workouts"] += 1

    weekly = []
    cursor = start - timedelta(days=start.weekday())
    last = date.today() - timedelta(days=date.today().weekday())
    while cursor <= last:
        b = buckets[cursor]
        weekly.append({
            "label": cursor.strftime("%d %b"),
            "week_start": cursor.isoformat(),
            "avg_steps": round(mean(b["steps"])) if b["steps"] else None,
            "adherence": round(b["action_done"] * 100 / b["action_total"]) if b["action_total"] else None,
            "workouts": b["workouts"],
        })
        cursor += timedelta(days=7)

    weight = [
        {"date": r["tracked_on"].strftime("%d %b"), "value": float(r["weight_kg"])}
        for r in daily if r.get("weight_kg") is not None
    ]
    return {"weekly": weekly, "weight": weight}


def get_dashboard_coaching_attention(clients: list[dict]) -> list[dict]:
    """Prioritise coaching attention using adherence/activity/workouts, not only scheduling."""
    today = date.today()
    output = []
    for client in clients:
        if client.get("status") != "active":
            continue
        cid = int(client["id"])
        recent = _row("""
            SELECT MAX(tracked_on) AS last_update
            FROM client_daily_tracking
            WHERE client_id = %s
        """, (cid,))
        last_update = recent.get("last_update") if recent else None
        reasons = []
        severity = 0

        if last_update is None:
            reasons.append("No tracking yet")
            severity += 2
        else:
            gap = (today - last_update).days
            if gap >= 3:
                reasons.append(f"No update for {gap} days")
                severity += 3
            elif gap == 2:
                reasons.append("No update for 2 days")
                severity += 2

        summary = get_client_weekly_summary(cid)
        if summary["action_percent"] is not None and summary["action_total"] >= 3:
            if summary["action_percent"] < 40:
                reasons.append(f"Actions {summary['action_percent']}%")
                severity += 3
            elif summary["action_percent"] < 65:
                reasons.append(f"Actions {summary['action_percent']}%")
                severity += 1

        if summary["workouts_assigned"] and summary["workouts_completed"] < summary["workouts_assigned"]:
            reasons.append(f"Workouts {summary['workouts_completed']}/{summary['workouts_assigned']}")
            severity += 1

        if reasons:
            output.append({
                "id": cid,
                "name": client.get("name") or f"Client {cid}",
                "week": client.get("current_week"),
                "reasons": reasons,
                "severity": severity,
                "href": f"/dashboard/clients/{cid}",
            })
    output.sort(key=lambda x: (-x["severity"], x["name"].lower()))
    return output[:8]


def get_previous_exercise_performance(client_id: int, assignment_id: int, exercise_title: str):
    rows = _rows("""
        SELECT a.workout_date, sl.set_number, sl.weight_kg, sl.reps, sl.completed
        FROM client_workout_set_logs sl
        JOIN client_workout_assignments a ON a.id = sl.assignment_id
        JOIN workout_exercises e ON e.id = sl.exercise_id
        WHERE a.client_id = %s
          AND a.id <> %s
          AND LOWER(TRIM(e.title)) = LOWER(TRIM(%s))
          AND a.status = 'completed'
        ORDER BY a.workout_date DESC NULLS LAST, a.id DESC, sl.set_number
    """, (client_id, assignment_id, exercise_title))
    if not rows:
        return None
    latest_date = rows[0]["workout_date"]
    same = [r for r in rows if r["workout_date"] == latest_date]
    return {
        "date": latest_date,
        "sets": [
            {"set_number": r["set_number"],
             "weight_kg": float(r["weight_kg"]) if r.get("weight_kg") is not None else None,
             "reps": r.get("reps"),
             "completed": bool(r.get("completed"))}
            for r in same
        ]
    }


def get_dashboard_client_coaching_signals(
    client_id: int,
    week_start: date,
    week_end: date,
    on_date: date,
) -> dict:
    """
    Coaching-only signals layered on top of the existing operational alerts.

    Rules deliberately avoid creating noise early in the coaching week:
    - low action adherence: <60%, from day 3 onward, with enough logged opportunities
    - workouts behind: completed sessions are below an evenly-paced expectation
      for the number of workouts assigned during this coaching week
    """
    day_number = max(1, min(7, (on_date - week_start).days + 1))

    action = _row("""
        SELECT
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE completed = TRUE)::int AS completed
        FROM client_action_daily_logs
        WHERE client_id = %s
          AND tracked_on BETWEEN %s AND %s
          AND tracked_on <= %s
    """, (client_id, week_start, week_end, on_date)) or {
        "total": 0,
        "completed": 0,
    }

    action_total = int(action.get("total") or 0)
    action_completed = int(action.get("completed") or 0)
    action_percent = (
        round(action_completed * 100 / action_total)
        if action_total
        else None
    )

    low_adherence = (
        day_number >= 3
        and action_total >= 3
        and action_percent is not None
        and action_percent < 60
    )

    workouts = _row("""
        SELECT
            COUNT(*)::int AS assigned,
            COUNT(*) FILTER (WHERE status = 'completed')::int AS completed
        FROM client_workout_assignments
        WHERE client_id = %s
          AND status <> 'removed'
          AND assigned_on BETWEEN %s AND %s
    """, (client_id, week_start, week_end)) or {
        "assigned": 0,
        "completed": 0,
    }

    workouts_assigned = int(workouts.get("assigned") or 0)
    workouts_completed = int(workouts.get("completed") or 0)

    # Example for 3 assigned sessions:
    # day 1-2 -> expected 0, day 3-4 -> expected 1,
    # day 5-6 -> expected 2, day 7 -> expected 3.
    expected_workouts = (
        (workouts_assigned * day_number) // 7
        if workouts_assigned
        else 0
    )
    if day_number == 7:
        expected_workouts = workouts_assigned

    workouts_behind = (
        workouts_assigned > 0
        and workouts_completed < expected_workouts
    )

    reasons = []
    if low_adherence:
        reasons.append(f"Action adherence {action_percent}%")
    if workouts_behind:
        reasons.append(
            f"Strength workouts {workouts_completed}/{workouts_assigned}"
        )

    return {
        "action_percent": action_percent,
        "action_total": action_total,
        "action_completed": action_completed,
        "low_adherence": low_adherence,
        "workouts_assigned": workouts_assigned,
        "workouts_completed": workouts_completed,
        "expected_workouts": expected_workouts,
        "workouts_behind": workouts_behind,
        "reasons": reasons,
    }
