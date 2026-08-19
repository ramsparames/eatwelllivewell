from datetime import date, timedelta

from app.database import get_connection


def create_macro_tracking_tables() -> None:
    """Create optional per-client macro settings and daily macro logs."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_macro_settings (
                    client_id INTEGER PRIMARY KEY
                        REFERENCES clients(id) ON DELETE CASCADE,
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    protein_target_g NUMERIC(8,2),
                    carbs_target_g NUMERIC(8,2),
                    fat_target_g NUMERIC(8,2),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS client_macro_logs (
                    id BIGSERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL
                        REFERENCES clients(id) ON DELETE CASCADE,
                    tracked_on DATE NOT NULL,
                    protein_g NUMERIC(8,2),
                    carbs_g NUMERIC(8,2),
                    fat_g NUMERIC(8,2),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (client_id, tracked_on)
                )
            """)


def _num(value):
    if value is None:
        return None
    return float(value)


def calculated_calories(protein_g, carbs_g, fat_g):
    if protein_g is None and carbs_g is None and fat_g is None:
        return None
    p = float(protein_g or 0)
    c = float(carbs_g or 0)
    f = float(fat_g or 0)
    return round((p * 4) + (c * 4) + (f * 9))


def get_macro_settings(client_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT client_id, enabled, protein_target_g,
                       carbs_target_g, fat_target_g
                FROM client_macro_settings
                WHERE client_id = %s
                LIMIT 1
            """, (client_id,))
            row = cursor.fetchone()
    if not row:
        return {
            "client_id": client_id,
            "enabled": False,
            "protein_target_g": None,
            "carbs_target_g": None,
            "fat_target_g": None,
            "calorie_target": None,
        }
    row["protein_target_g"] = _num(row.get("protein_target_g"))
    row["carbs_target_g"] = _num(row.get("carbs_target_g"))
    row["fat_target_g"] = _num(row.get("fat_target_g"))
    row["calorie_target"] = calculated_calories(
        row["protein_target_g"], row["carbs_target_g"], row["fat_target_g"]
    )
    return row


def save_macro_settings(
    client_id: int,
    enabled: bool,
    protein_target_g=None,
    carbs_target_g=None,
    fat_target_g=None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO client_macro_settings (
                    client_id, enabled, protein_target_g,
                    carbs_target_g, fat_target_g
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id)
                DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    protein_target_g = EXCLUDED.protein_target_g,
                    carbs_target_g = EXCLUDED.carbs_target_g,
                    fat_target_g = EXCLUDED.fat_target_g,
                    updated_at = NOW()
            """, (
                client_id, enabled, protein_target_g,
                carbs_target_g, fat_target_g,
            ))


def get_macro_log(client_id: int, tracked_on: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT client_id, tracked_on, protein_g, carbs_g, fat_g
                FROM client_macro_logs
                WHERE client_id = %s AND tracked_on = %s
                LIMIT 1
            """, (client_id, tracked_on))
            row = cursor.fetchone()
    if not row:
        return None
    row["protein_g"] = _num(row.get("protein_g"))
    row["carbs_g"] = _num(row.get("carbs_g"))
    row["fat_g"] = _num(row.get("fat_g"))
    row["calories"] = calculated_calories(
        row["protein_g"], row["carbs_g"], row["fat_g"]
    )
    return row


def save_macro_log(
    client_id: int,
    tracked_on: date,
    protein_g=None,
    carbs_g=None,
    fat_g=None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO client_macro_logs (
                    client_id, tracked_on, protein_g, carbs_g, fat_g
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id, tracked_on)
                DO UPDATE SET
                    protein_g = EXCLUDED.protein_g,
                    carbs_g = EXCLUDED.carbs_g,
                    fat_g = EXCLUDED.fat_g,
                    updated_at = NOW()
            """, (client_id, tracked_on, protein_g, carbs_g, fat_g))


def get_macro_logs_between(client_id: int, start_date: date, end_date: date):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT tracked_on, protein_g, carbs_g, fat_g
                FROM client_macro_logs
                WHERE client_id = %s
                  AND tracked_on BETWEEN %s AND %s
                ORDER BY tracked_on
            """, (client_id, start_date, end_date))
            rows = cursor.fetchall() or []
    result = {}
    for row in rows:
        row["protein_g"] = _num(row.get("protein_g"))
        row["carbs_g"] = _num(row.get("carbs_g"))
        row["fat_g"] = _num(row.get("fat_g"))
        row["calories"] = calculated_calories(
            row["protein_g"], row["carbs_g"], row["fat_g"]
        )
        result[row["tracked_on"]] = row
    return result


def get_macro_history(client_id: int, client_start_date: date | None, today: date):
    settings = get_macro_settings(client_id)
    if not settings["enabled"] or not client_start_date:
        return {"settings": settings, "by_date": {}, "week_summaries": {}}

    logs = get_macro_logs_between(client_id, client_start_date, today)
    summaries = {}

    for tracked_on, row in logs.items():
        week_number = ((tracked_on - client_start_date).days // 7) + 1
        bucket = summaries.setdefault(week_number, {
            "days_logged": 0, "protein": [], "carbs": [], "fat": [], "calories": []
        })
        if any(row.get(k) is not None for k in ("protein_g", "carbs_g", "fat_g")):
            bucket["days_logged"] += 1
        for source, dest in (
            ("protein_g", "protein"), ("carbs_g", "carbs"),
            ("fat_g", "fat"), ("calories", "calories")
        ):
            if row.get(source) is not None:
                bucket[dest].append(float(row[source]))

    for bucket in summaries.values():
        for key in ("protein", "carbs", "fat", "calories"):
            values = bucket[key]
            bucket[f"avg_{key}"] = round(sum(values) / len(values), 1) if values else None
            del bucket[key]

    return {"settings": settings, "by_date": logs, "week_summaries": summaries}
